from . import db, telegram as tg
from . import config
from .config import ADMIN_IDS

STATUS_FA = {
    "LOCKED": "🔒 قفل",
    "PENDING": "⏳ در انتظار شروع",
    "IN_PROGRESS": "🔄 در حال انجام",
    "DONE": "✅ تمام شده",
}

MAIN_MENU = tg.reply_keyboard([["🏠 شروع", "🛠 مدیریت", "📊 وضعیت"]])

# استیت‌هایی که وقتی فعال باشن، پیام متنیِ بعدیِ کاربر (نه دکمه) باید به‌عنوان ورودیِ ویزارد در نظر گرفته بشه
TEXT_AWAITING_STEPS = {
    "AWAITING_TITLE",
    "AWAITING_RENAME",
    "AWAITING_NEW_TASK",
    "AWAITING_HANDOFF_NOTE",
    "AWAITING_REPORT_REASON",
    "AWAITING_EDIT_TASK_NAME",
    "AWAITING_EDIT_ADD_TASK_NAME",
    "AWAITING_ADMIN_PASSWORD",
}


def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    member = db.get_member(user_id)
    return bool(member and member.get("is_admin"))


def member_label(member) -> str:
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

    if text == "/admin":
        db.set_admin_session(user["id"], {"step": "AWAITING_ADMIN_PASSWORD"})
        tg.send_message(chat_id, "رمز ادمین رو وارد کن:")
        return

    # دکمه‌های منوی پایین همیشه روی صفحه‌ن؛ حتی وسط یه ویزارد هم باید به‌عنوان دستور منو در نظر گرفته بشن،
    # نه به‌عنوان جواب سؤال جاریِ ویزارد
    if text in ("🏠 شروع", "🛠 مدیریت", "📊 وضعیت"):
        if text == "🏠 شروع":
            db.upsert_member(user["id"], user.get("username"), user.get("first_name"))
            tg.send_message(chat_id, "خوش اومدی 🙌", keyboard=MAIN_MENU)
        elif text == "🛠 مدیریت":
            show_admin_menu(chat_id, user["id"])
        elif text == "📊 وضعیت":
            show_status(chat_id, user["id"])
        return

    # هر کاربری (نه فقط ادمین) ممکنه وسط یه ویزارد متنی باشه (ساخت زنجیره، یادداشت، گزارش ایراد)
    session = db.get_admin_session(user["id"])
    if session.get("step") in TEXT_AWAITING_STEPS:
        try:
            handle_wizard_text(chat_id, user["id"], text, session)
        except Exception as e:
            print(f"[handlers] error in wizard text step: {e}")
            tg.send_message(chat_id, "⚠️ یه خطا پیش اومد. لطفاً دوباره از منو شروع کن.", keyboard=MAIN_MENU)
        return

    tg.send_message(chat_id, "متوجه نشدم؛ از دکمه‌های پایین استفاده کن.", keyboard=MAIN_MENU)


def handle_wizard_text(chat_id: int, user_id: int, text: str, session: dict):
    step = session["step"]

    if step == "AWAITING_ADMIN_PASSWORD":
        db.clear_admin_session(user_id)
        if config.ADMIN_PASSWORD and text == config.ADMIN_PASSWORD:
            db.set_member_admin(user_id, True)
            tg.send_message(chat_id, "✅ تبریک! شما الان ادمین این بات هستید.", keyboard=MAIN_MENU)
        else:
            tg.send_message(chat_id, "❌ رمز اشتباه بود.", keyboard=MAIN_MENU)
        return

    if step == "AWAITING_TITLE":
        session["title"] = text
        session["step"] = "SELECT_TEMPLATE"
        db.set_admin_session(user_id, session)
        show_template_picker(chat_id)
        return

    if step == "AWAITING_RENAME":
        idx = session["rename_index"]
        session["tasks"][idx]["name"] = text
        session["step"] = "EDIT_TASKS"
        db.set_admin_session(user_id, session)
        show_edit_tasks(chat_id, session)
        return

    if step == "AWAITING_NEW_TASK":
        if session.get("insert_pos") == "front":
            session["tasks"].insert(0, {"name": text})
        else:
            session["tasks"].append({"name": text})
        session["step"] = "EDIT_TASKS"
        db.set_admin_session(user_id, session)
        show_edit_tasks(chat_id, session)
        return

    if step == "AWAITING_HANDOFF_NOTE":
        if not text:
            tg.send_message(chat_id, "متن خالی بود؛ یادداشتت رو بنویس (یا برای رد کردن، یه خط تیره - بفرست):")
            return
        task_id = session["task_id"]
        note = None if text == "-" else text
        db.clear_admin_session(user_id)
        advance_chain(task_id, note)
        tg.send_message(chat_id, "✅ ثبت شد.", keyboard=MAIN_MENU)
        return

    if step == "AWAITING_REPORT_REASON":
        if not text:
            tg.send_message(chat_id, "متن ایراد خالی بود؛ لطفاً دوباره توضیح بده:")
            return
        origin_task_id = session["origin_task_id"]
        target_task_id = session["target_task_id"]
        db.clear_admin_session(user_id)
        target = db.get_task(target_task_id)
        chain = db.get_chain(target["chain_id"])
        db.set_task_note(target_task_id, text)
        db.set_task_status(target_task_id, "PENDING")
        db.create_revision(chain["id"], origin_task_id, target_task_id)
        target["note"] = text
        target["status"] = "PENDING"
        notify_revision(target, chain["title"], text)
        tg.send_message(chat_id, "✅ گزارش ثبت شد و به مسئولِ اون مرحله اطلاع داده شد.", keyboard=MAIN_MENU)
        return

    if step == "AWAITING_EDIT_TASK_NAME":
        if not text:
            tg.send_message(chat_id, "نام خالی بود؛ دوباره بنویس:")
            return
        task_id = session["task_id"]
        task = db.get_task(task_id)
        old_name = task["task_name"]
        db.rename_task(task_id, text)
        db.clear_admin_session(user_id)
        chain = db.get_chain(task["chain_id"])
        if task["status"] in ("PENDING", "IN_PROGRESS") and task.get("assigned_member_id"):
            tg.send_message(
                task["assigned_member_id"],
                f"ℹ️ نامِ مرحله‌ای که روش کار می‌کنی توی زنجیره‌ی «{chain['title']}» از «{old_name}» به «{text}» تغییر کرد.",
            )
        tg.send_message(chat_id, "✅ نام تسک تغییر کرد.")
        show_chain_detail(chat_id, task["chain_id"])
        return

    if step == "AWAITING_EDIT_ADD_TASK_NAME":
        if not text:
            tg.send_message(chat_id, "نام خالی بود؛ دوباره بنویس:")
            return
        chain_id = session["chain_id"]
        db.clear_admin_session(user_id)
        new_task = db.add_chain_task(chain_id, text)
        show_new_task_assignee_picker(chat_id, new_task["id"])
        return


# ============================================================ Admin menu / My tasks
def show_admin_menu(chat_id: int, user_id: int):
    if not is_admin(user_id):
        show_my_tasks(chat_id, user_id)
        return
    kb = tg.inline_keyboard([
        [("➕ زنجیره جدید", "newchain")],
        [("📂 زنجیره‌های فعال", "activechains")],
    ])
    tg.send_message(chat_id, "🛠 پنل مدیریت:", reply_markup=kb)


def show_my_tasks(chat_id: int, user_id: int):
    chains = db.get_active_chains()
    lines = []
    for c in chains:
        for t in c["tasks"]:
            if t.get("assigned_member_id") == user_id:
                assignee = member_label(db.get_member(user_id))
                lines.append(f"📋 {c['title']} — {t['task_name']}: {STATUS_FA[t['status']]} (👤 {assignee})")
    tg.send_message(chat_id, "\n".join(lines) if lines else "فعلاً هیچ وظیفه‌ای به شما اختصاص داده نشده.")


def show_status(chat_id: int, user_id: int):
    chains = db.get_active_chains()
    if not chains:
        tg.send_message(chat_id, "🚫 فعلاً هیچ زنجیره‌ی فعالی وجود نداره.")
        return

    if is_admin(user_id):
        rows = [[(c["title"], f"statuschain|{c['id']}")] for c in chains]
    else:
        my_chains = [c for c in chains if any(t.get("assigned_member_id") == user_id for t in c["tasks"])]
        if not my_chains:
            tg.send_message(chat_id, "فعلاً هیچ وظیفه‌ای به شما اختصاص داده نشده.")
            return
        rows = [[(c["title"], f"mystatuschain|{c['id']}")] for c in my_chains]

    tg.send_message(chat_id, "وضعیت کدوم زنجیره رو می‌خوای ببینی؟", reply_markup=tg.inline_keyboard(rows))


def show_chain_status(chat_id: int, chain_id: str):
    chain = db.get_chain(chain_id)
    if not chain:
        tg.send_message(chat_id, "⚠️ زنجیره پیدا نشد.")
        return
    lines = [f"📋 {chain['title']}"]
    for t in chain["tasks"]:
        assignee = member_label(db.get_member(t["assigned_member_id"])) if t.get("assigned_member_id") else "—"
        note_suffix = f" 📝{t['note']}" if t.get("note") else ""
        lines.append(f"  {t['order_index']+1}. {t['task_name']} — {STATUS_FA[t['status']]} (👤 {assignee}){note_suffix}")
    tg.send_message(chat_id, "\n".join(lines))


def show_my_chain_status(chat_id: int, chain_id: str, user_id: int):
    chain = db.get_chain(chain_id)
    if not chain:
        tg.send_message(chat_id, "⚠️ زنجیره پیدا نشد.")
        return
    mine = [t for t in chain["tasks"] if t.get("assigned_member_id") == user_id]
    if not mine:
        tg.send_message(chat_id, "توی این زنجیره وظیفه‌ای برای شما نیست.")
        return
    lines = [f"📋 {chain['title']}"]
    for t in mine:
        note_suffix = f" 📝{t['note']}" if t.get("note") else ""
        lines.append(f"{t['order_index']+1}. {t['task_name']} — {STATUS_FA[t['status']]}{note_suffix}")
    tg.send_message(chat_id, "\n".join(lines))


# ============================================================ New-chain wizard
def show_template_picker(chat_id: int):
    templates = db.get_templates()
    rows = [[(t["name"], f"tpl|{t['id']}")] for t in templates]
    tg.send_message(chat_id, "یه الگو انتخاب کن (بعداً می‌تونی ویرایشش کنی):", reply_markup=tg.inline_keyboard(rows))


def show_edit_tasks(chat_id: int, session: dict):
    rows = []
    n = len(session["tasks"])
    for i, t in enumerate(session["tasks"]):
        move_buttons = []
        if i > 0:
            move_buttons.append(("⬆️", f"taskup|{i}"))
        if i < n - 1:
            move_buttons.append(("⬇️", f"taskdown|{i}"))
        rows.append([(f"✏️ {i+1}. {t['name']}", f"taskedit|{i}")] + move_buttons + [("🗑", f"taskdel|{i}")])
    rows.append([("➕ افزودن به ابتدا", "taskaddfront"), ("➕ افزودن به انتها", "taskaddback")])
    rows.append([("✅ تایید و انتخاب مسئولین", "tasksconfirm")])
    tg.send_message(
        chat_id,
        f"📋 زنجیره: {session['title']}\n\nتسک‌ها رو ویرایش کن یا تایید بزن (با ⬆️⬇️ جابه‌جا کن):",
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
        saved_task["assigned_member_id"] = wanted["member_id"]  # کپی محلی رو هم‌سطح نگه می‌داریم

    notify_chain_overview(chain)

    first_task = chain["tasks"][0]
    db.set_task_status(first_task["id"], "PENDING")
    first_task["status"] = "PENDING"

    notify_assignee(first_task, chain["title"])

    for admin_uid in ADMIN_IDS:
        tg.send_message(admin_uid, f"✅ زنجیره «{chain['title']}» ساخته شد و اولین تسک ابلاغ شد.")

    db.clear_admin_session(admin_id)
    tg.send_message(chat_id, "🎉 زنجیره با موفقیت ساخته شد.", keyboard=MAIN_MENU)


def notify_chain_overview(chain: dict):
    """بلافاصله بعد از ساخت زنجیره، به هر عضو خبر می‌ده کل وظایفش توی این زنجیره چیه."""
    by_member = {}
    for t in chain["tasks"]:
        mid = t.get("assigned_member_id")
        if mid:
            by_member.setdefault(mid, []).append(t)

    for member_id, tasks in by_member.items():
        lines = [f"📋 زنجیره‌ی جدید: «{chain['title']}»\n\nوظایف شما در این زنجیره:"]
        for t in sorted(tasks, key=lambda x: x["order_index"]):
            lines.append(f"  {t['order_index']+1}. {t['task_name']}")
        lines.append("\nبه ترتیب که نوبتتون برسه، پیام جداگانه براتون می‌فرستیم.")
        tg.send_message(member_id, "\n".join(lines))


def notify_assignee(task: dict, chain_title: str):
    if not task.get("assigned_member_id"):
        return
    note_line = f"\n📝 یادداشت: {task['note']}\n" if task.get("note") else ""
    kb = tg.inline_keyboard([
        [
            ("🔄 در حال انجام", f"status|{task['id']}|IN_PROGRESS"),
            ("✅ تمام شد", f"status|{task['id']}|DONE"),
        ],
        [("⚠️ گزارش ایراد مرحله‌ی قبل", f"reportissue|{task['id']}")],
        [("🔁 واگذاری به فرد دیگر", f"reassign|{task['id']}")],
    ])
    tg.send_message(
        task["assigned_member_id"],
        f"📣 نوبت شما رسید:\n\n📋 زنجیره: {chain_title}\n🧩 تسک: {task['task_name']}\n{note_line}\nوضعیت رو اعلام کن:",
        reply_markup=kb,
    )


def notify_revision(task: dict, chain_title: str, reason: str):
    if not task.get("assigned_member_id"):
        return
    kb = tg.inline_keyboard([[
        ("🔄 در حال اصلاح", f"status|{task['id']}|IN_PROGRESS"),
        ("✅ اصلاح شد", f"status|{task['id']}|DONE"),
    ]])
    tg.send_message(
        task["assigned_member_id"],
        (
            f"⚠️ کاری که برای «{task['task_name']}» انجام داده بودی، نیاز به اصلاح داره.\n\n"
            f"📋 زنجیره: {chain_title}\n"
            f"📝 دلیل: {reason}\n\n"
            "لطفاً اصلاحش کن و بعد «✅ اصلاح شد» رو بزن."
        ),
        reply_markup=kb,
    )


def notify_transfer(task: dict, chain_title: str, from_label: str):
    if not task.get("assigned_member_id"):
        return
    note_line = f"\n📝 یادداشت: {task['note']}\n" if task.get("note") else ""
    kb = tg.inline_keyboard([
        [
            ("🔄 در حال انجام", f"status|{task['id']}|IN_PROGRESS"),
            ("✅ تمام شد", f"status|{task['id']}|DONE"),
        ],
        [("⚠️ گزارش ایراد مرحله‌ی قبل", f"reportissue|{task['id']}")],
        [("🔁 واگذاری به فرد دیگر", f"reassign|{task['id']}")],
    ])
    tg.send_message(
        task["assigned_member_id"],
        (
            f"🔁 مسئولیتِ این مرحله از طرف {from_label} به شما واگذار شد.\n\n"
            f"📋 زنجیره: {chain_title}\n🧩 تسک: {task['task_name']}\n{note_line}\nوضعیت رو اعلام کن:"
        ),
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
        note_suffix = f" 📝{t['note']}" if t.get("note") else ""
        text_lines.append(f"{t['order_index']+1}. {t['task_name']} — {STATUS_FA[t['status']]} (👤 {assignee}){note_suffix}")
        rows.append([
            (f"👤 مسئولِ «{t['task_name']}»", f"reassign|{t['id']}"),
            ("✏️", f"edittaskname|{t['id']}"),
            ("🗑", f"edittaskdel|{t['id']}"),
        ])
    rows.append([("➕ افزودن تسک به این زنجیره", f"editaddtask|{chain_id}")])
    rows.append([("🗑 حذف کل زنجیره", f"deletechain|{chain_id}")])
    tg.send_message(chat_id, "\n".join(text_lines), reply_markup=tg.inline_keyboard(rows))


def show_reassign_picker(chat_id: int, task_id: str):
    members = db.get_members()
    if not members:
        tg.send_message(chat_id, "🚫 عضوی برای انتخاب وجود نداره.")
        return
    rows = [[(member_label(m), f"reassignpick|{task_id}|{m['id']}")] for m in members]
    tg.send_message(chat_id, "مسئول جدید رو انتخاب کن:", reply_markup=tg.inline_keyboard(rows))


def show_new_task_assignee_picker(chat_id: int, task_id: str):
    members = db.get_members()
    if not members:
        tg.send_message(chat_id, "🚫 عضوی برای انتخاب وجود نداره.")
        return
    rows = [[(member_label(m), f"editassign|{task_id}|{m['id']}")] for m in members]
    tg.send_message(chat_id, "مسئولِ این تسک جدید رو انتخاب کن:", reply_markup=tg.inline_keyboard(rows))


def reassign_task(chat_id: int, task_id: str, new_member_id: int, from_user_id: int):
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
        from_label = member_label(db.get_member(from_user_id)) or "مدیر"
        notify_transfer(task, chain["title"], from_label)


# ============================================================ Revision report (send an earlier stage back for fixes)
def show_report_picker(chat_id: int, task_id: str):
    task = db.get_task(task_id)
    chain = db.get_chain(task["chain_id"])
    earlier = [t for t in chain["tasks"] if t["order_index"] < task["order_index"] and t["status"] == "DONE"]
    if not earlier:
        tg.send_message(chat_id, "مرحله‌ی قبلیِ تمام‌شده‌ای برای گزارش دادن وجود نداره.")
        return
    rows = [[(f"{t['order_index']+1}. {t['task_name']}", f"reportpick|{t['id']}")] for t in earlier]
    tg.send_message(chat_id, "کدوم مرحله نیاز به اصلاح داره؟", reply_markup=tg.inline_keyboard(rows))


def delete_chain_task_flow(chat_id: int, task_id: str):
    task = db.get_task(task_id)
    if not task:
        tg.send_message(chat_id, "⚠️ تسک پیدا نشد.")
        return
    chain_id = task["chain_id"]
    deleted_index = task["order_index"]
    was_active = task["status"] in ("PENDING", "IN_PROGRESS")
    assignee_id = task.get("assigned_member_id")
    task_name = task["task_name"]

    db.delete_chain_task(task_id)
    db.reindex_chain_tasks(chain_id)
    chain = db.get_chain(chain_id)

    tg.send_message(chat_id, f"🗑 تسک «{task_name}» حذف شد.")

    if was_active and assignee_id:
        tg.send_message(
            assignee_id,
            f"ℹ️ مرحله‌ی «{task_name}» از زنجیره‌ی «{chain['title']}» حذف شد؛ دیگه نیازی به انجامش نیست.",
        )
        # تسکی که جای حذف‌شده نشسته (اگه قفل بود) باید فعال بشه، چون دیگه چیزی جلوش نیست
        next_task = next((t for t in chain["tasks"] if t["order_index"] == deleted_index), None)
        if next_task and next_task["status"] == "LOCKED":
            db.set_task_status(next_task["id"], "PENDING")
            next_task["status"] = "PENDING"
            if next_task.get("assigned_member_id"):
                notify_assignee(next_task, chain["title"])


def assign_new_task_flow(chat_id: int, task_id: str, member_id: int):
    db.set_task_assignee(task_id, member_id)
    task = db.get_task(task_id)
    chain = db.get_chain(task["chain_id"])
    tg.send_message(chat_id, f"✅ مسئولِ «{task['task_name']}» تنظیم شد.")

    prev_tasks = [t for t in chain["tasks"] if t["order_index"] < task["order_index"]]
    if all(t["status"] == "DONE" for t in prev_tasks):
        db.set_task_status(task["id"], "PENDING")
        task["status"] = "PENDING"
        notify_assignee(task, chain["title"])

    show_chain_detail(chat_id, chain["id"])


def delete_chain_flow(chat_id: int, chain_id: str):
    chain = db.get_chain(chain_id)
    if not chain:
        tg.send_message(chat_id, "⚠️ زنجیره پیدا نشد.")
        return

    notified = set()
    for t in chain["tasks"]:
        member_id = t.get("assigned_member_id")
        if member_id and t["status"] in ("PENDING", "IN_PROGRESS") and member_id not in notified:
            tg.send_message(member_id, f"🗑 زنجیره‌ی «{chain['title']}» کامل حذف شد؛ دیگه نیازی به ادامه‌ی وظایفش نیست.")
            notified.add(member_id)

    db.delete_chain(chain_id)
    tg.send_message(chat_id, f"🗑 زنجیره‌ی «{chain['title']}» کامل حذف شد.", keyboard=MAIN_MENU)


# ============================================================ Callback queries
def handle_callback(cq: dict):
    data = cq["data"]
    chat_id = cq["message"]["chat"]["id"]
    user_id = cq["from"]["id"]
    tg.answer_callback_query(cq["id"])

    try:
        _dispatch_callback(data, chat_id, user_id)
    except KeyError as e:
        print(f"[handlers] missing session key {e} — session probably lost/corrupted")
        tg.send_message(
            chat_id,
            "⚠️ ارتباط قطع شده بود و مرحله‌ی قبلی ناقص موند. لطفاً از «🛠 مدیریت» دوباره شروع کن.",
        )
    except Exception as e:
        print(f"[handlers] unexpected error in callback: {e}")
        tg.send_message(chat_id, "⚠️ یه خطای غیرمنتظره پیش اومد. دوباره امتحان کن.")


def _dispatch_callback(data: str, chat_id: int, user_id: int):
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

    elif action == "taskup":
        session = db.get_admin_session(user_id)
        idx = int(parts[1])
        if idx > 0:
            session["tasks"][idx - 1], session["tasks"][idx] = session["tasks"][idx], session["tasks"][idx - 1]
            db.set_admin_session(user_id, session)
        show_edit_tasks(chat_id, session)

    elif action == "taskdown":
        session = db.get_admin_session(user_id)
        idx = int(parts[1])
        if idx < len(session["tasks"]) - 1:
            session["tasks"][idx + 1], session["tasks"][idx] = session["tasks"][idx], session["tasks"][idx + 1]
            db.set_admin_session(user_id, session)
        show_edit_tasks(chat_id, session)

    elif action == "taskaddfront":
        session = db.get_admin_session(user_id)
        session["step"] = "AWAITING_NEW_TASK"
        session["insert_pos"] = "front"
        db.set_admin_session(user_id, session)
        tg.send_message(chat_id, "نام تسکی که می‌خوای به ابتدای زنجیره اضافه بشه رو بفرست:")

    elif action == "taskaddback":
        session = db.get_admin_session(user_id)
        session["step"] = "AWAITING_NEW_TASK"
        session["insert_pos"] = "back"
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

    elif action == "statuschain":
        show_chain_status(chat_id, parts[1])

    elif action == "mystatuschain":
        show_chain_status(chat_id, parts[1])

    elif action == "reassign":
        show_reassign_picker(chat_id, parts[1])

    elif action == "reassignpick":
        reassign_task(chat_id, parts[1], int(parts[2]), user_id)

    elif action == "edittaskname":
        db.set_admin_session(user_id, {"step": "AWAITING_EDIT_TASK_NAME", "task_id": parts[1]})
        tg.send_message(chat_id, "نام جدید این تسک رو بفرست:")

    elif action == "edittaskdel":
        delete_chain_task_flow(chat_id, parts[1])

    elif action == "editaddtask":
        db.set_admin_session(user_id, {"step": "AWAITING_EDIT_ADD_TASK_NAME", "chain_id": parts[1]})
        tg.send_message(chat_id, "نام تسک جدید رو بفرست:")

    elif action == "editassign":
        assign_new_task_flow(chat_id, parts[1], int(parts[2]))

    elif action == "deletechain":
        if not is_admin(user_id):
            return
        chain = db.get_chain(parts[1])
        kb = tg.inline_keyboard([[("⚠️ بله، کامل حذف کن", f"deletechainconfirm|{parts[1]}")]])
        tg.send_message(chat_id, f"مطمئنی می‌خوای زنجیره‌ی «{chain['title']}» رو کامل حذف کنی؟ این کار قابل بازگشت نیست.", reply_markup=kb)

    elif action == "deletechainconfirm":
        if not is_admin(user_id):
            return
        delete_chain_flow(chat_id, parts[1])

    elif action == "status":
        handle_status_change(chat_id, user_id, parts[1], parts[2])

    elif action == "proceed":
        advance_chain(parts[1], None)
        tg.send_message(chat_id, "✅ ثبت شد.")

    elif action == "addnote":
        db.set_admin_session(user_id, {"step": "AWAITING_HANDOFF_NOTE", "task_id": parts[1]})
        tg.send_message(chat_id, "یادداشتت رو برای مرحله‌ی بعد بفرست:")

    elif action == "reportissue":
        db.set_admin_session(user_id, {"step": "CHOOSING_REPORT_TARGET", "origin_task_id": parts[1]})
        show_report_picker(chat_id, parts[1])

    elif action == "reportpick":
        session = db.get_admin_session(user_id)
        origin_task_id = session.get("origin_task_id")
        target_task_id = parts[1]
        db.set_admin_session(
            user_id,
            {"step": "AWAITING_REPORT_REASON", "origin_task_id": origin_task_id, "target_task_id": target_task_id},
        )
        tg.send_message(chat_id, "چه ایرادی بوده؟ توضیح بده:")


def handle_status_change(chat_id: int, user_id: int, task_id: str, new_status: str):
    task = db.get_task(task_id)
    if not task:
        tg.send_message(chat_id, "⚠️ این تسک دیگه معتبر نیست.")
        return

    db.set_task_status(task_id, new_status)
    tg.send_message(chat_id, f"✅ وضعیت «{task['task_name']}» ثبت شد: {STATUS_FA[new_status]}")

    if new_status != "DONE":
        return

    revisions = db.get_unresolved_revisions_for_target(task_id)
    if revisions:
        # این یه اصلاحِ گزارش‌شده بود، نه پیشرفتِ عادیِ زنجیره — باید کنترل به همون مرحله‌ای
        # که گزارش رو داده بود برگرده (نه به مرحله‌ی بعدیِ ترتیب اصلی)
        db.resolve_revisions_for_target(task_id)
        seen_origins = set()
        for rev in revisions:
            origin_id = rev["origin_task_id"]
            if origin_id in seen_origins:
                continue
            seen_origins.add(origin_id)
            if not db.get_unresolved_revisions_for_origin(origin_id):
                resume_origin(origin_id)
        return

    kb = tg.inline_keyboard([[
        ("➡️ بدون یادداشت", f"proceed|{task_id}"),
        ("✍️ نوشتن یادداشت برای بعدی", f"addnote|{task_id}"),
    ]])
    tg.send_message(chat_id, "یادداشتی برای نفر بعدی داری؟", reply_markup=kb)


def resume_origin(origin_task_id: str):
    """همه‌ی ایرادهایی که از این مرحله گزارش شده بودن رفع شدن؛ به مسئولش خبر بده که ادامه بده."""
    origin = db.get_task(origin_task_id)
    if not origin or not origin.get("assigned_member_id"):
        return
    chain = db.get_chain(origin["chain_id"])
    tg.send_message(
        origin["assigned_member_id"],
        f"✅ ایراد(های)ی که برای مراحلِ قبلِ «{origin['task_name']}» گزارش داده بودی رفع شد.\n"
        f"📋 زنجیره: {chain['title']}\nمی‌تونی به کارت ادامه بدی.",
    )


def advance_chain(task_id: str, note: str = None):
    task = db.get_task(task_id)
    chain = db.get_chain(task["chain_id"])
    tasks = chain["tasks"]
    next_task = next((t for t in tasks if t["order_index"] == task["order_index"] + 1), None)

    if next_task is None:
        db.set_chain_status(chain["id"], "COMPLETED")
        for admin_uid in ADMIN_IDS:
            tg.send_message(admin_uid, f"🏁 زنجیره «{chain['title']}» به طور کامل تمام شد.")
        return

    if note:
        db.set_task_note(next_task["id"], note)
        next_task["note"] = note
    db.set_task_status(next_task["id"], "PENDING")
    next_task["status"] = "PENDING"

    if next_task.get("assigned_member_id"):
        notify_assignee(next_task, chain["title"])
    else:
        for admin_uid in ADMIN_IDS:
            tg.send_message(admin_uid, f"⚠️ تسک بعدیِ «{next_task['task_name']}» مسئول نداره؛ از پنل مدیریت مشخص کن.")
