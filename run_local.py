"""
اجرای محلی بات با polling — هیچ نیازی به وبهوک، سرور، یا هاست نداره.
فقط برای تست و توسعه روی کامپیوتر خودت.
"""

from dotenv import load_dotenv
load_dotenv()  # مقادیر رو از فایل .env می‌خونه

import time
import requests
from bot.config import TELEGRAM_API
from bot.handlers import handle_update


def run():
    offset = None
    print("🤖 بات با حالت polling در حال اجراست... (برای توقف Ctrl+C بزن)")
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            resp = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=35)
            resp.raise_for_status()
            updates = resp.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                try:
                    handle_update(u)
                except Exception as e:
                    print(f"⚠️ خطا در پردازش پیام: {e}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ خطای شبکه، ۳ ثانیه دیگه دوباره امتحان می‌کنم: {e}")
            time.sleep(3)


if __name__ == "__main__":
    run()