-- ============================================================
-- TaskFlow Bot — Supabase / Postgres schema
-- این فایل رو یک‌بار توی Supabase SQL Editor اجرا کن (Project > SQL Editor > New query)
-- ============================================================

create extension if not exists "pgcrypto"; -- برای gen_random_uuid()

-- افرادی که با /start عضو ربات شدن
create table if not exists members (
    id bigint primary key,               -- آی‌دی عددی تلگرام
    username text,
    first_name text,
    registered_at timestamptz not null default now()
);

-- الگوهای از پیش تعریف‌شده‌ی زنجیره (سرگروه می‌تونه ازشون شروع کنه و ویرایش کنه)
create table if not exists templates (
    id serial primary key,
    name text not null,
    task_names text[] not null      -- ترتیب پیش‌فرض تسک‌ها
);

-- خود زنجیره‌ها
create table if not exists chains (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    leader_id bigint not null references members(id),
    status text not null default 'ACTIVE',   -- ACTIVE | COMPLETED
    created_at timestamptz not null default now()
);

-- تسک‌های هر زنجیره، به ترتیب
create table if not exists chain_tasks (
    id uuid primary key default gen_random_uuid(),
    chain_id uuid not null references chains(id) on delete cascade,
    order_index int not null,
    task_name text not null,
    assigned_member_id bigint references members(id),
    status text not null default 'LOCKED',   -- LOCKED | PENDING | IN_PROGRESS | DONE
    updated_at timestamptz not null default now()
);
create index if not exists idx_chain_tasks_chain on chain_tasks(chain_id);

-- استیت موقتِ ویزارد ادمین (چون سرورلسه و بین درخواست‌ها چیزی توی رم نمی‌مونه)
create table if not exists admin_sessions (
    admin_id bigint primary key,
    state jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

-- الگوی پیش‌فرض شبیه TaskFlow / بات قبلی (۷ مرحله)
insert into templates (name, task_names)
values (
    'استاندارد (۷ مرحله)',
    array['خوانش', 'بازبینی خوانش', 'ساخت عکس‌نوشته', 'بازبینی عکس‌نوشته', 'انطباق محتوا', 'ساخت ویدیو', 'بازبینی ویدیو']
)
on conflict do nothing;

insert into templates (name, task_names)
values (
    'ساده (۳ مرحله)',
    array['تولید محتوا', 'بازبینی', 'انتشار']
)
on conflict do nothing;
