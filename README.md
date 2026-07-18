# TaskFlowChain Bot

> A Telegram bot for chain-based task workflows — inspired by [TaskFlow](https://github.com/mnfarzaneh/TaskFlow), an Android app I built for sequential task management. Instead of writing a dedicated backend for multi-user communication, I used Telegram itself as the messaging/identity/notification layer.

**Highlights**
- Fully serverless-style architecture: **PythonAnywhere** (Flask webhook) + **Supabase** (Postgres via REST) — zero fixed hosting cost.
- No `python-telegram-bot`; raw HTTP calls to the Bot API, chosen deliberately to fit a stateless request/response model.
- Chain-based task flow with sequential unlocking, revision/rework cycles (report an issue on an earlier stage, it reopens and control returns to the reporter once fixed), self-service task handoff between users, live chain editing, and runtime admin promotion via a password command.

**Stack:** Python · Flask · Supabase (Postgres) · Telegram Bot API · PythonAnywhere

**Architecture**
```
Telegram user
     │
     ▼
Telegram Bot API ── webhook ──▶ PythonAnywhere (Flask, api/webhook.py)
                                        │
                                        ▼
                              Supabase (Postgres via REST)
```

---

## توضیحاتِ کامل (فارسی)

بات تلگرامیِ مدیریتِ زنجیره‌ایِ وظایف — الهام‌گرفته از اپلیکیشنِ اندرویدیِ [TaskFlow](https://github.com/mnfarzaneh/TaskFlow)، با این تفاوت که به‌جای بک‌اندِ اختصاصی، از خودِ زیرساختِ تلگرام (پیام‌رسانی، هویت، نوتیفیکیشن) استفاده می‌کنه.

سرگروه یه زنجیره از مراحل می‌سازه، هر مرحله رو به یکی از اعضا محول می‌کنه، و هر مرحله فقط وقتی نوبتش برسه (مرحله‌ی قبلش تمام بشه) به مسئولش پیام می‌ده.

### معماری

بدون هیچ سرورِ همیشه‌روشن یا هزینه‌ی ماهانه:

- **اجرا:** [PythonAnywhere](https://www.pythonanywhere.com) — یه وب‌اپِ Flask که با وبهوک تلگرام کار می‌کنه؛ فقط وقتی واقعاً پیامی برسه «بیدار» می‌شه.
- **دیتابیس:** [Supabase](https://supabase.com) (Postgres، سطحِ رایگان) — چون هر اجرا مستقل و بی‌حافظه‌ست، همه‌ی استیت (زنجیره‌ها، تسک‌ها، اعضا، حتی استیتِ موقتِ ویزارد) توی دیتابیس نگه داشته می‌شه.
- بدون `python-telegram-bot`؛ ارتباط مستقیم و خام با Bot API از طریق `requests`.

هردو سرویس سطحِ رایگان دارن؛ محدودیت‌هاشون در بخشِ «محدودیت‌ها» پایین‌تر توضیح داده شده.

### قابلیت‌ها

- **ثبتِ اعضا:** هرکس با `/start` عضو می‌شه.
- **ساختِ زنجیره:** انتخاب از بین الگوهای آماده، ویرایشِ تسک‌ها (تغییرِ نام، حذف، افزودن به ابتدا/انتها، جابه‌جاییِ ترتیب با ⬆️⬇️)، و تخصیصِ مسئولِ هر مرحله از بین اعضای ثبت‌شده.
- **پیشرویِ خودکار:** با «✅ تمام شد» زدنِ هر مرحله، مرحله‌ی بعدی خودکار باز و به مسئولش اطلاع داده می‌شه.
- **گزارشِ ایراد / چرخه‌ی اصلاح:** هرکسی می‌تونه از مراحلِ قبلیِ تمام‌شده ایراد بگیره؛ اون مرحله دوباره باز و مسئولش با دلیلِ ایراد مطلع می‌شه. اگه چند مرحله هم‌زمان گزارش بشه، فقط بعد از رفعِ **همه‌شون** کنترل به مرحله‌ای که گزارش رو داده برمی‌گرده (نه مرحله‌ی بعدیِ ترتیبِ عادی).
- **یادداشتِ هندآف:** موقعِ اتمامِ هر مرحله، امکانِ نوشتنِ یادداشت برای نفرِ بعدی.
- **واگذاریِ خودخواسته:** خودِ فرد می‌تونه مسئولیتِ تسکش رو به فردِ دیگه‌ای واگذار کنه؛ گیرنده پیامِ واضحِ «مسئولیت از طرفِ X به شما واگذار شد» می‌گیره (نه پیامِ عمومیِ نوبت).
- **ویرایشِ زنجیره‌ی فعال:** تغییرِ مسئول، تغییرِ نامِ تسک، حذفِ تسک، افزودنِ تسکِ جدید به یه زنجیره‌ی درحال‌اجرا — با اطلاع‌رسانیِ خودکار به فردِ تحتِ‌تأثیر.
- **حذفِ کاملِ زنجیره:** با تأییدِ دوم، همراه با اطلاع‌رسانی به هرکی تسکِ فعال داشته.
- **وضعیتِ فیلترشده:** انتخابِ یه زنجیره‌ی خاص از لیست، به‌جای دیدنِ همه‌چیز یک‌جا؛ هم برای ادمین هم برای کاربرِ عادی (با نامِ مسئولِ هر مرحله).
- **ادمین‌شدن با رمز:** دستورِ `/admin` + واردکردنِ رمز، بدون نیاز به دخالتِ دستیِ توسعه‌دهنده.

### ساختارِ فایل‌ها

```
taskflow-bot/
├── api/
│   └── webhook.py        # اندپوینتِ Flask که PythonAnywhere صداش می‌زنه
├── bot/
│   ├── config.py          # خواندنِ متغیرهای محیطی
│   ├── db.py               # لایه‌ی دیتابیس (Supabase REST)
│   ├── telegram.py         # ارتباطِ خام با Bot API
│   └── handlers.py         # کلِ منطقِ بات
├── run_local.py            # اجرای محلی با polling، برای تست بدون هاست
├── schema.sql              # ساختارِ اولیه‌ی جداول
├── migration_00X.sql       # تغییراتِ بعدیِ دیتابیس (به‌ترتیب اجرا بشن)
└── requirements.txt
```

### راه‌اندازی

**۱) بات در BotFather**
`/newbot` بزن و توکن رو بگیر (این توکن هیچ‌وقت توی کد یا گیت‌هاب نره — فقط توی متغیرهای محیطی).

**۲) دیتابیس در Supabase**
پروژه‌ی رایگان بساز، بعد به‌ترتیب توی SQL Editor اجرا کن:
1. `schema.sql`
2. `migration_001.sql` (رفعِ تکرارِ الگوها + ستونِ یادداشت)
3. `migration_002.sql` (جدولِ `revisions` برای چرخه‌ی اصلاح)
4. `migration_003.sql` (ستونِ `is_admin` برای ادمین‌شدن با رمز)

از `Project Settings → API`، مقدارِ `Project URL` و کلیدِ `service_role` (یا `Secret key` در نسخه‌های جدید) رو بردار.

**۳) دیپلوی روی PythonAnywhere**
1. حسابِ رایگان بساز (فقط ایمیل لازمه، نه شماره).
2. از Bash console: `git clone <آدرسِ ریپو>`
3. از تبِ **Web** → Add a new web app → Flask → Python 3.10+.
4. فایلِ WSGI (لینکش توی همون تبِ Web) رو این‌طوری تنظیم کن:

```python
import sys, os

os.environ["HTTP_PROXY"] = "http://proxy.server:3128"
os.environ["HTTPS_PROXY"] = "http://proxy.server:3128"

path = '/home/<یوزرنیم>/taskflow-bot'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["BOT_TOKEN"] = "..."
os.environ["WEBHOOK_SECRET"] = "..."
os.environ["ADMIN_IDS"] = "..."
os.environ["ADMIN_PASSWORD"] = "..."
os.environ["SUPABASE_URL"] = "..."
os.environ["SUPABASE_SERVICE_KEY"] = "..."

from api.webhook import app as application
```

5. Reload بزن.

**۴) وصل‌کردنِ وبهوک**
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<یوزرنیم>.pythonanywhere.com/api/webhook&secret_token=<WEBHOOK_SECRET>
```

### اجرای محلی (بدون هاست، فقط برای تست)

```bash
python -m venv venv
venv\Scripts\activate      # ویندوز
pip install flask requests python-dotenv
```
فایلِ `.env` بساز، وبهوکِ فعلی رو خاموش کن (`.../deleteWebhook`)، بعد:
```bash
python run_local.py
```

### محدودیت‌های سطحِ رایگان

- **PythonAnywhere:** وب‌اپ اگه یک ماه هیچ فعالیتی نبینه، غیرفعال (نه پاک) می‌شه؛ کافیه دوباره وارد حساب بشی و تمدیدش کنی.
- **Supabase:** پروژه اگه ۷ روز هیچ کوئریِ واقعی نگیره، Pause می‌شه؛ از داشبورد دوباره فعالش کن (اولین درخواستِ بعدش چند ثانیه طول می‌کشه).

برای یه گروهِ فعال، این محدودیت‌ها معمولاً هیچ‌وقت لمس نمی‌شن.

### نکاتِ امنیتی
- `BOT_TOKEN`، `SUPABASE_SERVICE_KEY`، و `ADMIN_PASSWORD` فقط توی فایلِ WSGI (PythonAnywhere) یا `.env` (محلی) — هیچ‌وقت توی گیت‌هاب یا کدِ کامیت‌شده.
- `.gitignore` باید شاملِ `.env`, `.env.*`, `venv/` باشه.
