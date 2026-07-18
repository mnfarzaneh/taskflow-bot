# TaskFlowChain Bot

> A Telegram bot for chain-based task workflows — inspired by [TaskFlow](https://github.com/mnfarzaneh/TaskFlow), an Android app I built for sequential task management. Instead of writing a dedicated backend for multi-user communication, this project uses Telegram itself as the messaging/identity/notification layer.

**Highlights**
- Serverless-style architecture: **PythonAnywhere** (Flask webhook) + **Supabase** (Postgres via REST) — no fixed hosting cost.
- No `python-telegram-bot`; raw HTTP calls to the Bot API, chosen to fit a stateless request/response model.
- Chain-based task flow with sequential unlocking, revision/rework cycles (an earlier stage can be reopened with a note, and control returns to the reporting stage once every reopened stage is fixed), self-service task handoff between users, live chain editing, and runtime admin promotion via a password command.

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

## توضیحات کامل (فارسی)

TaskFlowChain یک ربات تلگرامی برای مدیریت زنجیره‌ای وظایف است. این ربات به یک مدیر گروه (سرگروه) امکان می‌دهد یک زنجیره از مراحل بسازد، هر مرحله را به یکی از اعضا اختصاص دهد، و ترتیب اجرا را کنترل کند: هر مرحله فقط زمانی به مسئولش اطلاع داده می‌شود که مرحله‌ی قبلی تکمیل شده باشد.

این پروژه از اپلیکیشن اندرویدی TaskFlow الهام گرفته شده، با این تفاوت که برای ارتباط بین کاربران، به‌جای نوشتن یک بک‌اند اختصاصی، از زیرساخت خودِ تلگرام (پیام‌رسانی، هویت کاربران، و نوتیفیکیشن) استفاده شده است.

### معماری

اجرای این ربات به هیچ سرور همیشه‌روشن یا هزینه‌ی ثابت ماهانه نیاز ندارد:

- **اجرا:** [PythonAnywhere](https://www.pythonanywhere.com) — یک وب‌اپ Flask که از طریق وبهوک تلگرام فراخوانی می‌شود؛ کد فقط زمانی اجرا می‌شود که پیامی واقعی برسد.
- **دیتابیس:** [Supabase](https://supabase.com) (Postgres، سطح رایگان) — چون هر اجرا مستقل و بدون حافظه‌ی داخلی است، تمام وضعیت (زنجیره‌ها، تسک‌ها، اعضا، و حتی وضعیت موقتِ ویزاردهای چندمرحله‌ای) در دیتابیس نگه‌داری می‌شود.
- ارتباط با تلگرام بدون کتابخانه‌ی `python-telegram-bot` و از طریق فراخوانی مستقیمِ Bot API با کتابخانه‌ی `requests` انجام می‌شود.

هر دو سرویس دارای سطح رایگان با محدودیت‌های مشخص هستند؛ جزئیات در بخش «محدودیت‌های سطح رایگان» آمده است.

### قابلیت‌ها

- **ثبت اعضا:** هر کاربر با ارسال `/start` در سیستم ثبت می‌شود.
- **ساخت زنجیره:** انتخاب از میان الگوهای از‌پیش‌تعریف‌شده، ویرایش تسک‌ها (تغییر نام، حذف، افزودن به ابتدا یا انتها، جابه‌جایی ترتیب با دکمه‌های ⬆️/⬇️)، و تعیین مسئول هر مرحله از میان اعضای ثبت‌شده.
- **پیشروی خودکار:** با ثبت وضعیت «تمام شد» برای هر مرحله، مرحله‌ی بعدی به‌طور خودکار باز شده و به مسئولش اطلاع داده می‌شود.
- **گزارش ایراد و چرخه‌ی اصلاح:** هر کاربر می‌تواند نسبت به یک مرحله‌ی قبلیِ تکمیل‌شده گزارش ایراد ثبت کند؛ آن مرحله دوباره باز شده و مسئولش همراه با دلیل ایراد مطلع می‌شود. اگر چند مرحله هم‌زمان گزارش شوند، فقط پس از اصلاح همه‌ی آن‌ها، کنترل به مرحله‌ای که گزارش را ثبت کرده بازمی‌گردد (نه به مرحله‌ی بعدیِ ترتیب عادی زنجیره).
- **یادداشت هنگام تحویل:** در لحظه‌ی تکمیل هر مرحله، امکان نوشتن یادداشت برای نفر بعدی وجود دارد.
- **واگذاری داوطلبانه:** هر کاربر می‌تواند مسئولیت تسک خود را به فرد دیگری واگذار کند؛ فرد گیرنده پیامی روشن دریافت می‌کند («مسئولیت این مرحله از طرف [نام واگذارکننده] به شما واگذار شد»)، نه پیام عمومیِ اعلام نوبت.
- **ویرایش زنجیره‌ی فعال:** تغییر مسئول، تغییر نام تسک، حذف تسک، و افزودن تسک جدید به یک زنجیره‌ی در حال اجرا — همراه با اطلاع‌رسانی خودکار به فردی که تحت تأثیر تغییر قرار می‌گیرد.
- **حذف کامل زنجیره:** پس از یک مرحله‌ی تأیید، همراه با اطلاع‌رسانی به هر کسی که در آن لحظه تسک فعالی داشته باشد.
- **مشاهده‌ی وضعیت به تفکیک زنجیره:** به‌جای نمایش همه‌چیز یک‌جا، ابتدا انتخاب یک زنجیره‌ی مشخص از فهرست، سپس نمایش جزئیات همان زنجیره (شامل نام مسئول هر مرحله)، هم برای مدیر و هم برای کاربر عادی.
- **ارتقا به سطح مدیر با رمز:** با ارسال دستور `/admin` و وارد کردن رمز عبور، کاربر بدون نیاز به دخالت دستیِ توسعه‌دهنده می‌تواند به سطح مدیر ارتقا یابد.

### ساختار فایل‌ها

```
taskflow-bot/
├── api/
│   └── webhook.py        # اندپوینت Flask که PythonAnywhere آن را فراخوانی می‌کند
├── bot/
│   ├── config.py          # خواندن متغیرهای محیطی
│   ├── db.py               # لایه‌ی دسترسی به دیتابیس (Supabase REST)
│   ├── telegram.py         # ارتباط مستقیم با Bot API تلگرام
│   └── handlers.py         # کل منطق ربات
├── run_local.py            # اجرای محلی با روش polling، برای تست بدون نیاز به هاست
├── schema.sql              # ساختار اولیه‌ی جداول دیتابیس
├── migration_00X.sql       # تغییرات بعدیِ ساختار دیتابیس (باید به‌ترتیب اجرا شوند)
└── requirements.txt
```

هر فایل migration مربوط به یک قابلیت مشخص از ربات است:

| فایل | هدف |
|---|---|
| `schema.sql` | ساخت جداول اولیه (اعضا، الگوها، زنجیره‌ها، تسک‌ها) |
| `migration_001.sql` | جلوگیری از تکرار در جدول الگوها و افزودن ستون یادداشت به تسک‌ها |
| `migration_002.sql` | ساخت جدول `revisions` برای پیاده‌سازیِ چرخه‌ی اصلاح |
| `migration_003.sql` | افزودن ستون `is_admin` برای قابلیت ارتقا به مدیر با رمز |

### راه‌اندازی

**۱) ساخت ربات در BotFather**
با ارسال `/newbot` به [@BotFather](https://t.me/BotFather) یک ربات جدید ساخته و توکن آن دریافت می‌شود. این توکن هرگز نباید در کد یا مخزن گیت‌هاب قرار گیرد؛ فقط باید در متغیرهای محیطی ذخیره شود.

**۲) ساخت دیتابیس در Supabase**
پس از ساخت یک پروژه‌ی رایگان، فایل‌های زیر باید به‌ترتیب در SQL Editor اجرا شوند:
1. `schema.sql`
2. `migration_001.sql`
3. `migration_002.sql`
4. `migration_003.sql`

سپس از مسیر `Project Settings → API`، مقدار `Project URL` و کلید `service_role` (یا `Secret key` در نسخه‌های جدیدتر داشبورد) برداشته می‌شود.

**۳) دیپلوی روی PythonAnywhere**
1. ساخت یک حساب رایگان (فقط ایمیل لازم است، بدون نیاز به شماره تلفن).
2. از طریق Bash console: `git clone <آدرس مخزن>`
3. از تب **Web**: گزینه‌ی Add a new web app → انتخاب Flask → انتخاب Python 3.10 یا بالاتر.
4. فایل WSGI (لینک آن در همان تب Web موجود است) باید به این شکل تنظیم شود:

```python
import sys, os

os.environ["HTTP_PROXY"] = "http://proxy.server:3128"
os.environ["HTTPS_PROXY"] = "http://proxy.server:3128"

path = '/home/<username>/taskflow-bot'
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

5. زدن دکمه‌ی Reload.

**۴) اتصال وبهوک به تلگرام**
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<username>.pythonanywhere.com/api/webhook&secret_token=<WEBHOOK_SECRET>
```

### اجرای محلی (بدون نیاز به هاست، صرفاً برای تست)

```bash
python -m venv venv
venv\Scripts\activate      # ویندوز
pip install flask requests python-dotenv
```
یک فایل `.env` با متغیرهای لازم ساخته می‌شود، وبهوک فعال با فراخوانی `.../deleteWebhook` غیرفعال می‌شود، و سپس:
```bash
python run_local.py
```

### محدودیت‌های سطح رایگان

- **PythonAnywhere:** در صورتی که وب‌اپ به مدت یک ماه هیچ فعالیتی نداشته باشد، غیرفعال می‌شود (نه حذف)؛ برای فعال‌سازی مجدد کافی است وارد حساب شده و آن را تمدید کرد.
- **Supabase:** در صورتی که پروژه به مدت ۷ روز هیچ درخواست واقعی به دیتابیس دریافت نکند، به حالت Pause می‌رود؛ فعال‌سازی مجدد از طریق داشبورد انجام می‌شود و اولین درخواست پس از آن چند ثانیه طول می‌کشد.

برای یک گروه با فعالیت منظم، این محدودیت‌ها معمولاً هیچ‌گاه مانع کار نمی‌شوند.

### نکات امنیتی
- مقادیر `BOT_TOKEN`، `SUPABASE_SERVICE_KEY`، و `ADMIN_PASSWORD` فقط باید در فایل WSGI (روی PythonAnywhere) یا فایل `.env` (در محیط محلی) قرار بگیرند؛ هرگز در کد یا مخزن گیت‌هاب.
- فایل `.gitignore` باید شامل `.env`, `.env.*`, و `venv/` باشد.
