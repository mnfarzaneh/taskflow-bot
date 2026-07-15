from . import db, telegram as tg
from .config import ADMIN_IDS

STATUS_FA = {
    "LOCKED": "🔒 قفل",
    "PENDING": "⏳ در انتظار شروع",
    "IN_PROGRESS": "🔄 در حال انجام",
    "DONE": "✅ تمام شده",
}

MAIN_MENU = tg.reply_keyboard([["🏠 شروع", "🛠 مدیریت", "📊 وضعیت"]])


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def member_label(member: dict | None) -> str:
    if not member:
        return "—"
    return member.get("first_name") or (f"@{member['username']}" if member.get("username") else str(member["id"]))


# ============================================================ Entry point
def handle_update(update: dict):
    if "message" in update:
        handle_message(update["message"])
    elif "callback_query" in update:
        handle_callback(update["callback_query"])


# ============================================================ Messages
def handle_message(message: dict):
    chat_id = message["chat"]["id"]
    user = message["from"]
    text = (message.get("text") or "").strip()

    if text == "/start":
        db.upsert_member(user["id"], user.get("username"), user.get("first_name"))
        tg.send_message(chat_id, "👋 خوش اومدی! با موفقیت عضو شدی.", keyboard=MAIN_MENU)
        return

    # اگه ادمینه و وسط ویزارد ساخت زنجیره‌ست، اول اون رو چک کن
    if is_admin(user["id"]):
        session = db.get_admin_session(user["id"])
        if session.get("step") in ("AWAITING_TITLE", "AWAITING_RENAME", "AWAITING_NEW_TASK"):
            handle_wizard_text(chat_id, user["id"], text, session)
            return

    if text == "🏠 شروع":
        db.upsert_member(user["id"], user.get("username"), user.get("first_name"))
        tg.send_message(chat_id, "خوش اومدی 🙌", keyboard=MAIN_MENU)
    elif text == "🛠 مدیریت":
        show_admin_menu(chat_id, user["id"])
    elif text == "📊 وضعیت":
        show_status(chat_id, user["id"])
    else:
        tg.send_message(chat_id, "متوجه نشدم؛ از دکمه‌های پایین استفاده کن.", keyboard=MAIN_MENU)


def handle_wizard_text(chat_id: int, admin_id: int, text: str, session: dict):
    step = session["step"]

    if step == "AWAITING_TITLE":
        session["title"] = text
        session["step"] = "SELECT_TEMPLATE"
        db.set_admin_session(admin_id, session)
        show_template_picker(chat_id)
        return

    if step == "AWAITING_RENAME":
        idx = session["rename_index"]
        session["tasks"][idx]["name"] = text
        session["step"] = "EDIT_TASKS"
        db.set_admin_session(admin_id, session)
        show_edit_tasks(chat_id, session)
        return

    if step == "AWAITING_NEW_TASK":
        session["tasks"].append({"name": text})
        session["step"] = "EDIT_TASKS"
        db.set_admin_session(admin_id, session)
        show_edit_tasks(chat_id, session)
        return


# ============================================================ Admin menu
def show_admin_menu(chat_id: int, user_id: int):
    if not is_admin(user_id):
        tg.send_message(chat_id, "⛔️ این بخش فقط برای سرگروه‌هاست.")
        return
    kb = tg.inline_keyboard([
        [("➕ زنجیره جدید", "newchain")],
        [("📂 زنجیره‌های فعال", "activechains")],
    ])
    tg.send_message(chat_id, "🛠 پنل مدیریت:", reply_markup=kb)


def show_status(chat_id: int, user_id: int):
    chains = db.get_active_chains()
    if not chains:
        tg.send_message(chat_id, "🚫 فعلاً هیچ زنجیره‌ی فعالی وجود نداره.")
        return

    if is_admin(user_id):
        lines = []
        for c in chains:
            lines.append(f"\n📋 {c['title']}")
            for t in c["tasks"]:
                assignee = member_label(db.get_member(t["assigned_member_id"])) if t.get("assigned_member_id") else "—"
                lines.append(f"  {t['order_index']+1}. {t['task_name']} — {STATUS_FA[t['status']]} (👤 {assignee})")
        tg.send_message(chat_id, "\n".join(lines))
    else:
        lines = []
        for c in chains:
            my_tasks = [t for t in c["tasks"] if t.get("assigned_member_id") == user_id]
            for t in my_tasks:
                lines.append(f"📋 {c['title']} — {t['task_name']}: {STATUS_FA[t['status']]}")
        tg.send_message(chat_id, "\n".join(lines) if lines else "فعلاً تسکی به شما اختصاص داده نشده.")


# ============================================================ New-chain wizard
def show_template_picker(chat_id: int):
    templates = db.get_templates()
    rows = [[(t["name"], f"tpl|{t['id']}")] for t in templates]
    tg.send_message(chat_id, "یه الگو انتخاب کن (بعداً می‌تونی ویرایشش کنی):", reply_markup=tg.inline_keyboard(rows))


def show_edit_tasks(chat_id: int, session: dict):
    rows = []
    for i, t in enumerate(session["tasks"]):
        rows.append([(f"✏️ {i+1}. {t['name']}", f"taskedit|{i}"), ("🗑", f"taskdel|{i}")])
    rows.append([("➕ افزودن تسک", "taskadd")])
    rows.append([("✅ تایید و انتخاب مسئولین", "tasksconfirm")])
    tg.send_message(
        chat_id,
        f"📋 زنجیره: {session['title']}\n\nتسک‌ها رو ویرایش کن یا تایید بزن:",
        reply_markup=tg.inline_keyboard(rows),
    )


def show_assign_step(chat_id: int, session: dict):
    idx = session["assign_index"]
    members = db.get_members()
    if not members:
        tg.send_message(chat_id, "🚫 هنوز هیچ‌کس با /start عضو ربات نشده. اول باید افراد گروه عضو بشن.")
        return
    task_name = session["tasks"][idx]["name"]
    rows = [[(member_label(m), f"assignpick|{m['id']}")] for m in members]
    tg.send_message(
        chat_id,
        f"مسئول تسک «{task_name}» ({idx+1}/{len(session['tasks'])}) رو انتخاب کن:",
        reply_markup=tg.inline_keyboard(rows),
    )


def finalize_chain(chat_id: int, admin_id: int, session: dict):
    chain = db.create_chain(session["title"], admin_id, [t["name"] for t in session["tasks"]])
    for saved_task, wanted in zip(chain["tasks"], session["tasks"]):
        db.set_task_assignee(saved_task["id"], wanted["member_id"])

    first_task = chain["tasks"][0]
    db.set_task_status(first_task["id"], "PENDING")

    notify_assignee(first_task, chain["title"])

    for admin_uid in ADMIN_IDS:
        tg.send_message(admin_uid, f"✅ زنجیره «{chain['title']}» ساخته شد و اولین تسک ابلاغ شد.")

    db.clear_admin_session(admin_id)
    tg.send_message(chat_id, "🎉 زنجیره با موفقیت ساخته شد.", keyboard=MAIN_MENU)


def notify_assignee(task: dict, chain_title: str):
    if not task.get("assigned_member_id"):
        return
    kb = tg.inline_keyboard([[
        ("🔄 در حال انجام", f"status|{task['id']}|IN_PROGRESS"),
        ("✅ تمام شد", f"status|{task['id']}|DONE"),
    ]])
    tg.send_message(
        task["assigned_member_id"],
        f"📣 نوبت شما رسید:\n\n📋 زنجیره: {chain_title}\n🧩 تسک: {task['task_name']}\n\nوضعیت رو اعلام کن:",
        reply_markup=kb,
    )


# ============================================================ Active chains view / reassignment
def show_active_chains_list(chat_id: int):
    chains = db.get_active_chains()
    if not chains:
        tg.send_message(chat_id, "🚫 زنجیره‌ی فعالی وجود نداره.")
        return
    rows = [[(c["title"], f"viewchain|{c['id']}")] for c in chains]
    tg.send_message(chat_id, "یکی رو انتخاب کن:", reply_markup=tg.inline_keyboard(rows))


def show_chain_detail(chat_id: int, chain_id: str):
    chain = db.get_chain(chain_id)
    if not chain:
        tg.send_message(chat_id, "⚠️ زنجیره پیدا نشد.")
        return
    text_lines = [f"📋 {chain['title']}\n"]
    rows = []
    for t in chain["tasks"]:
        assignee = member_label(db.get_member(t["assigned_member_id"])) if t.get("assigned_member_id") else "—"
        text_lines.append(f"{t['order_index']+1}. {t['task_name']} — {STATUS_FA[t['status']]} (👤 {assignee})")
        rows.append([(f"✏️ تغییر مسئولِ «{t['task_name']}»", f"reassign|{t['id']}")])
    tg.send_message(chat_id, "\n".join(text_lines), reply_markup=tg.inline_keyboard(rows))


def show_reassign_picker(chat_id: int, task_id: str):
    members = db.get_members()
    if not members:
        tg.send_message(chat_id, "🚫 عضوی برای انتخاب وجود نداره.")
        return
    rows = [[(member_label(m), f"reassignpick|{task_id}|{m['id']}")] for m in members]
    tg.send_message(chat_id, "مسئول جدید رو انتخاب کن:", reply_markup=tg.inline_keyboard(rows))


def reassign_task(chat_id: int, task_id: str, new_member_id: int):
    old_task = db.get_task(task_id)
    if not old_task:
        tg.send_message(chat_id, "⚠️ تسک پیدا نشد.")
        return
    old_member_id = old_task.get("assigned_member_id")

    db.set_task_assignee(task_id, new_member_id)
    task = db.get_task(task_id)
    chain = db.get_chain(task["chain_id"])

    tg.send_message(chat_id, f"✅ مسئولِ «{task['task_name']}» تغییر کرد.")

    if old_member_id and old_member_id != new_member_id and task["status"] in ("PENDING", "IN_PROGRESS"):
        tg.send_message(old_member_id, f"ℹ️ تسک «{task['task_name']}» از زنجیره‌ی «{chain['title']}» از شما گرفته شد.")

    if task["status"] in ("PENDING", "IN_PROGRESS"):
        notify_assignee(task, chain["title"])


# ============================================================ Callback queries
def handle_callback(cq: dict):
    data = cq["data"]
    chat_id = cq["message"]["chat"]["id"]
    user_id = cq["from"]["id"]
    tg.answer_callback_query(cq["id"])

    parts = data.split("|")
    action = parts[0]

    if action == "newchain":
        if not is_admin(user_id):
            return
        db.set_admin_session(user_id, {"step": "AWAITING_TITLE"})
        tg.send_message(chat_id, "عنوان زنجیره‌ی جدید رو بفرست:")

    elif action == "activechains":
        show_active_chains_list(chat_id)

    elif action == "tpl":
        template = db.get_template(int(parts[1]))
        session = db.get_admin_session(user_id)
        session["tasks"] = [{"name": n} for n in template["task_names"]]
        session["step"] = "EDIT_TASKS"
        db.set_admin_session(user_id, session)
        show_edit_tasks(chat_id, session)

    elif action == "taskedit":
        session = db.get_admin_session(user_id)
        session["step"] = "AWAITING_RENAME"
        session["rename_index"] = int(parts[1])
        db.set_admin_session(user_id, session)
        tg.send_message(chat_id, "نام جدید این تسک رو بفرست:")

    elif action == "taskdel":
        session = db.get_admin_session(user_id)
        idx = int(parts[1])
        if len(session["tasks"]) > 1:
            session["tasks"].pop(idx)
            db.set_admin_session(user_id, session)
        show_edit_tasks(chat_id, session)

    elif action == "taskadd":
        session = db.get_admin_session(user_id)
        session["step"] = "AWAITING_NEW_TASK"
        db.set_admin_session(user_id, session)
        tg.send_message(chat_id, "نام تسک جدید رو بفرست:")

    elif action == "tasksconfirm":
        session = db.get_admin_session(user_id)
        session["step"] = "ASSIGN_TASKS"
        session["assign_index"] = 0
        db.set_admin_session(user_id, session)
        show_assign_step(chat_id, session)

    elif action == "assignpick":
        session = db.get_admin_session(user_id)
        idx = session["assign_index"]
        session["tasks"][idx]["member_id"] = int(parts[1])
        session["assign_index"] += 1
        if session["assign_index"] < len(session["tasks"]):
            db.set_admin_session(user_id, session)
            show_assign_step(chat_id, session)
        else:
            finalize_chain(chat_id, user_id, session)

    elif action == "viewchain":
        show_chain_detail(chat_id, parts[1])

    elif action == "reassign":
        show_reassign_picker(chat_id, parts[1])

    elif action == "reassignpick":
        reassign_task(chat_id, parts[1], int(parts[2]))

    elif action == "status":
        handle_status_change(chat_id, parts[1], parts[2])


def handle_status_change(chat_id: int, task_id: str, new_status: str):
    task = db.get_task(task_id)
    if not task:
        tg.send_message(chat_id, "⚠️ این تسک دیگه معتبر نیست.")
        return

    db.set_task_status(task_id, new_status)
    chain = db.get_chain(task["chain_id"])
    tg.send_message(chat_id, f"✅ وضعیت «{task['task_name']}» ثبت شد: {STATUS_FA[new_status]}")

    if new_status != "DONE":
        return

    tasks = chain["tasks"]
    next_task = next((t for t in tasks if t["order_index"] == task["order_index"] + 1), None)

    if next_task is None:
        db.set_chain_status(chain["id"], "COMPLETED")
        for admin_uid in ADMIN_IDS:
            tg.send_message(admin_uid, f"🏁 زنجیره «{chain['title']}» به طور کامل تمام شد.")
        return

    db.set_task_status(next_task["id"], "PENDING")
    next_task["status"] = "PENDING"
    if next_task.get("assigned_member_id"):
        notify_assignee(next_task, chain["title"])
    else:
        for admin_uid in ADMIN_IDS:
            tg.send_message(admin_uid, f"⚠️ تسک بعدیِ «{next_task['task_name']}» مسئول نداره؛ از پنل مدیریت مشخص کن.")
