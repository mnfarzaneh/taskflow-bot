import requests
from .config import TELEGRAM_API


def _call(method: str, payload: dict) -> dict:
    r = requests.post(f"{TELEGRAM_API}/{method}", json=payload, timeout=10)
    if not r.ok:
        print(f"[telegram] {method} failed: {r.status_code} {r.text}")
    return r.json() if r.content else {}


def send_message(chat_id: int, text: str, reply_markup: dict = None, keyboard=None) -> dict:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    elif keyboard is not None:
        payload["reply_markup"] = keyboard
    return _call("sendMessage", payload)


def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict = None) -> dict:
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _call("editMessageText", payload)


def answer_callback_query(callback_query_id: str, text: str = None) -> dict:
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return _call("answerCallbackQuery", payload)


def set_webhook(url: str, secret_token: str) -> dict:
    return _call("setWebhook", {"url": url, "secret_token": secret_token})


def inline_keyboard(rows: list) -> dict:
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": data} for text, data in row]
            for row in rows
        ]
    }


def reply_keyboard(rows: list) -> dict:
    return {"keyboard": rows, "resize_keyboard": True}