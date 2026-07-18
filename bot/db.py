"""
لایه دیتابیس — همه‌چیز از طریق Supabase REST (PostgREST) انجام می‌شه.
چون هر اجرای serverless مستقل و بی‌حافظه‌ست، هیچ استیتی توی رم نگه نمی‌داریم؛
هرچی لازمه (از جمله استیت موقت ویزارد ادمین) توی دیتابیس ذخیره می‌شه.
"""

import time
import requests
from .config import SUPABASE_URL, SUPABASE_KEY

_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def _url(path: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{path}"


def _with_retry(fn, *args, **kwargs):
    """اتصال به Supabase گاهی به‌خاطر شبکه‌ی ناپایدار قطع می‌شه؛ یه‌بار دوباره امتحان می‌کنیم قبل از شکست کامل."""
    try:
        return fn(*args, **kwargs)
    except requests.exceptions.RequestException as e:
        print(f"[db] network hiccup, retrying once: {e}")
        time.sleep(1)
        return fn(*args, **kwargs)


def _get(table: str, params: dict) -> list:
    def do():
        r = requests.get(_url(table), headers=_HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    return _with_retry(do)


def _insert(table: str, payload, params: dict = None) -> list:
    def do():
        headers = {**_HEADERS, "Prefer": "return=representation"}
        r = requests.post(_url(table), headers=headers, json=payload, params=params or {}, timeout=15)
        r.raise_for_status()
        return r.json()
    return _with_retry(do)


def _upsert(table: str, payload, on_conflict: str) -> list:
    def do():
        headers = {**_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
        r = requests.post(
            _url(table), headers=headers, json=payload,
            params={"on_conflict": on_conflict}, timeout=15,
        )
        r.raise_for_status()
        return r.json()
    return _with_retry(do)


def _patch(table: str, params: dict, payload: dict) -> list:
    def do():
        headers = {**_HEADERS, "Prefer": "return=representation"}
        r = requests.patch(_url(table), headers=headers, params=params, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    return _with_retry(do)


def _delete(table: str, params: dict) -> None:
    def do():
        r = requests.delete(_url(table), headers=_HEADERS, params=params, timeout=15)
        r.raise_for_status()
    return _with_retry(do)


# ============================================================ Members
def upsert_member(user_id: int, username: str, first_name: str) -> dict:
    rows = _upsert(
        "members",
        {"id": user_id, "username": username, "first_name": first_name},
        on_conflict="id",
    )
    return rows[0] if rows else {"id": user_id, "username": username, "first_name": first_name}


def get_members() -> list:
    return _get("members", {"select": "*", "order": "registered_at.desc"})


def get_member(user_id: int) -> dict | None:
    rows = _get("members", {"select": "*", "id": f"eq.{user_id}"})
    return rows[0] if rows else None


def set_member_admin(user_id: int, is_admin: bool) -> dict:
    rows = _patch("members", {"id": f"eq.{user_id}"}, {"is_admin": is_admin})
    return rows[0] if rows else None


# ============================================================ Templates
def get_templates() -> list:
    return _get("templates", {"select": "*", "order": "id.asc"})


def get_template(template_id: int) -> dict | None:
    rows = _get("templates", {"select": "*", "id": f"eq.{template_id}"})
    return rows[0] if rows else None


# ============================================================ Chains + Tasks
def create_chain(title: str, leader_id: int, task_names: list) -> dict:
    """یک زنجیره‌ی جدید با تسک‌های LOCKED می‌سازه (بدون مسئول هنوز)."""
    chain = _insert("chains", {"title": title, "leader_id": leader_id})[0]
    tasks_payload = [
        {"chain_id": chain["id"], "order_index": i, "task_name": name, "status": "LOCKED"}
        for i, name in enumerate(task_names)
    ]
    tasks = _insert("chain_tasks", tasks_payload)
    chain["tasks"] = sorted(tasks, key=lambda t: t["order_index"])
    return chain


def get_chain(chain_id: str) -> dict | None:
    rows = _get("chains", {"select": "*", "id": f"eq.{chain_id}"})
    if not rows:
        return None
    chain = rows[0]
    chain["tasks"] = get_chain_tasks(chain_id)
    return chain


def get_active_chains() -> list:
    chains = _get("chains", {"select": "*", "status": "eq.ACTIVE", "order": "created_at.desc"})
    for c in chains:
        c["tasks"] = get_chain_tasks(c["id"])
    return chains


def get_chain_tasks(chain_id: str) -> list:
    return _get(
        "chain_tasks",
        {"select": "*", "chain_id": f"eq.{chain_id}", "order": "order_index.asc"},
    )


def get_task(task_id: str) -> dict | None:
    rows = _get("chain_tasks", {"select": "*", "id": f"eq.{task_id}"})
    return rows[0] if rows else None


def set_task_assignee(task_id: str, member_id: int) -> dict:
    rows = _patch("chain_tasks", {"id": f"eq.{task_id}"}, {"assigned_member_id": member_id})
    return rows[0]


def set_task_status(task_id: str, status: str) -> dict:
    rows = _patch(
        "chain_tasks", {"id": f"eq.{task_id}"},
        {"status": status, "updated_at": "now()"},
    )
    return rows[0]


def set_chain_status(chain_id: str, status: str) -> None:
    _patch("chains", {"id": f"eq.{chain_id}"}, {"status": status})


def set_task_note(task_id: str, note: str) -> dict:
    rows = _patch("chain_tasks", {"id": f"eq.{task_id}"}, {"note": note})
    return rows[0] if rows else None


# ============================================================ Revisions (send-back-for-fix tracking)
def create_revision(chain_id: str, origin_task_id: str, target_task_id: str) -> None:
    _insert("revisions", {"chain_id": chain_id, "origin_task_id": origin_task_id, "target_task_id": target_task_id})


def get_unresolved_revisions_for_target(target_task_id: str) -> list:
    return _get("revisions", {"select": "*", "target_task_id": f"eq.{target_task_id}", "resolved": "eq.false"})


def resolve_revisions_for_target(target_task_id: str) -> None:
    _patch("revisions", {"target_task_id": f"eq.{target_task_id}", "resolved": "eq.false"}, {"resolved": True})


def get_unresolved_revisions_for_origin(origin_task_id: str) -> list:
    return _get("revisions", {"select": "*", "origin_task_id": f"eq.{origin_task_id}", "resolved": "eq.false"})


# ============================================================ Editing an existing chain's structure
def rename_task(task_id: str, new_name: str) -> dict:
    rows = _patch("chain_tasks", {"id": f"eq.{task_id}"}, {"task_name": new_name})
    return rows[0] if rows else None


def delete_chain_task(task_id: str) -> None:
    _delete("chain_tasks", {"id": f"eq.{task_id}"})


def reindex_chain_tasks(chain_id: str) -> None:
    """بعد از حذف/افزودنِ یه تسک، شماره‌ی ترتیبِ بقیه رو پشت‌سرهم می‌کنه (بدون شکاف)."""
    tasks = get_chain_tasks(chain_id)
    for i, t in enumerate(tasks):
        if t["order_index"] != i:
            _patch("chain_tasks", {"id": f"eq.{t['id']}"}, {"order_index": i})


def add_chain_task(chain_id: str, task_name: str) -> dict:
    tasks = get_chain_tasks(chain_id)
    next_index = max([t["order_index"] for t in tasks], default=-1) + 1
    rows = _insert("chain_tasks", {
        "chain_id": chain_id, "order_index": next_index, "task_name": task_name, "status": "LOCKED",
    })
    return rows[0]


def delete_chain(chain_id: str) -> None:
    _delete("chains", {"id": f"eq.{chain_id}"})


# ============================================================ Admin wizard session
def get_admin_session(admin_id: int) -> dict:
    rows = _get("admin_sessions", {"select": "*", "admin_id": f"eq.{admin_id}"})
    return rows[0]["state"] if rows else {}


def set_admin_session(admin_id: int, state: dict) -> None:
    _upsert("admin_sessions", {"admin_id": admin_id, "state": state}, on_conflict="admin_id")


def clear_admin_session(admin_id: int) -> None:
    _delete("admin_sessions", {"admin_id": f"eq.{admin_id}"})
