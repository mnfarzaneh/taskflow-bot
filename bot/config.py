import os

# ---- Telegram ----
BOT_TOKEN = os.environ["BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# مقدار دلخواهی که خودت انتخاب می‌کنی و موقع setWebhook هم می‌فرستی
# تلگرام این مقدار رو توی هدر هر درخواست برمی‌گردونه تا مطمئن بشیم درخواست واقعاً از تلگرامه
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# آی‌دی عددی سرگروه‌ها/ادمین‌ها، جدا شده با کاما. مثال: "56732144,76653571"
ADMIN_IDS = {
    int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()
}

# رمزی که هر کاربر با وارد کردنش (دستور /admin) می‌تونه خودش رو ادمین کنه
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# ---- Supabase ----
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")          # مثل https://xxxx.supabase.co
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]              # service_role key — فقط سمت سرور!
