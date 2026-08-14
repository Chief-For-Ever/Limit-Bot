import logging
import random
import string
import sqlite3
import datetime
import jdatetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ============ تنظیمات ============
BOT_TOKEN = "8753659672:AAH0tHsxH3YAG6Ogf8aJUTzGfIzS5e6gSow"
ADMIN_CHAT_ID = 1252988484
DB = "students.db"
# ==================================

logging.basicConfig(level=logging.INFO)

# ---------- دکمه‌های دانش‌آموز ----------
BTN_PANEL = "🪪 پنل کاربری"
BTN_MESSAGE = "💬 ارسال پیام"
BTN_VIDEO = "🎥 ویدیو"
BTN_JOZVE = "📄 جزوه"
BTN_BACK = "🔙 بازگشت"

SCHOOL_BTNS = ["🏫 شاهد شهید چمران", "🏫 شهید بهشتی", "🏫 سایر"]

# ---------- دکمه‌های ادمین: منوی اصلی ----------
ABTN_CODES = "🔑 کدها"
ABTN_STUDENTS = "👥 لیست دانش‌آموزان"
ABTN_CONTENT = "📚 لیست جزوات/ویدیوها"
ABTN_BROADCAST = "📢 پیام همگانی"
ABTN_BACK_MAIN = "🔙 بازگشت به منوی اصلی"

# ---------- زیرمنوی کدها ----------
CBTN_ACTIVE = "🟢 در حال استفاده"
CBTN_EXPIRED = "🔴 منقضی شده"
CBTN_SCHEDULED = "🕓 برنامه‌ریزی‌شده"
CBTN_DELETED = "🗑 حذف شده"
CBTN_ADD = "➕ افزودن کد"
CBTN_DEL = "❌ حذف کد"
CBTN_SET_FILE = "🎬 تنظیم فایل یک کد"

DBTN_SINGLE = "👤 حذف تکی"
DBTN_GROUP = "👥 حذف گروهی"
DBTN_ALL = "💥 حذف همگانی"

SCOPE_BTNS = ["🏫 بر اساس مدرسه", "📚 بر اساس رشته"]
MAJOR_BTNS = ["🧪 تجربی", "➗ ریاضی", "📖 انسانی"]
MAJOR_BTNS_LIMITED = ["🧪 تجربی", "➗ ریاضی"]
SUBTYPE_BTNS = ["🟣 Actual", "🔵 Tactical", "⚪️ Scout"]
TARGET_BTNS = ["🧪 تجربی", "➗ ریاضی", "🌐 همه"]

# ---------- زیرمنوی دانش‌آموزان ----------
SBTN_SEARCH = "🔍 جستجو"

# ---------- زیرمنوی محتوا (placeholder) ----------
CONTENT_BTNS = ["🧪 تجربی ۱", "🧪 تجربی ۲", "➗ ریاضی ۱", "➗ ریاضی ۲", "📖 انسانی ۱", "📖 انسانی ۲"]

# ---------- زیرمنوی پیام همگانی ----------
BBTN_PERSON = "👤 شخص خاص"
BBTN_SCHOOL = "🏫 دانش‌آموزان مدرسه"
BBTN_MAJOR = "📚 رشته خاص"
BBTN_ALL = "📢 همه کاربران"

ABTN_ADD_VIDEO = "🎥 افزودن ویدیو"
ABTN_ADD_JOZVE = "📄 افزودن جزوه"
ABTN_DONE = "✅ اتمام و بازگشت"

SUBTYPE_EMOJI = {"actual": "🟣", "tactical": "🔵", "scout": "⚪️"}
SUBTYPE_LABEL = {"actual": "Actual", "tactical": "Tactical", "scout": "Scout"}
SCHOOL_LABEL = {"chamran": "شاهد شهید چمران", "beheshti": "شهید بهشتی", "other": "سایر"}
MAJOR_LABEL = {"tajrobi": "تجربی", "riazi": "ریاضی", "ensani": "انسانی"}

user_state = {}                               # دانش‌آموز: مرحله فعلی
admin_flow = {"step": None, "data": {}}       # ادمین: مدیریت مراحل
admin_upload_state = {"pending": None}
forward_map = {}


# ============ دیتابیس ============

def db():
    return sqlite3.connect(DB)


def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS students (
        telegram_id INTEGER PRIMARY KEY, code TEXT,
        first_name TEXT, last_name TEXT, phone TEXT, school TEXT,
        registered_at TEXT, message_count INTEGER DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS codes (
        code TEXT PRIMARY KEY, sub_type TEXT, school TEXT, major TEXT,
        created_at TEXT, expiry_date TEXT, activation_date TEXT,
        is_deleted INTEGER DEFAULT 0,
        video_file_id TEXT, video_type TEXT, jozve_file_id TEXT, jozve_type TEXT)""")
    conn.commit()
    conn.close()


def reset_admin_flow():
    admin_flow["step"] = None
    admin_flow["data"] = {}


# ============ تاریخ ============

def compute_expiry():
    today = jdatetime.date.today()
    if today.month >= 6:
        expiry = jdatetime.date(today.year + 1, 4, 1)
    else:
        expiry = jdatetime.date(today.year, 4, 1)
    return expiry.togregorian().isoformat()


def today_iso():
    return datetime.date.today().isoformat()


def get_status(sub_type, expiry_date, activation_date, is_deleted):
    if is_deleted:
        return "deleted"
    today = today_iso()
    if activation_date and today < activation_date:
        return "scheduled"
    if sub_type != "scout" and expiry_date and today > expiry_date:
        return "expired"
    return "active"


def remaining_text(sub_type, expiry_date):
    if sub_type == "scout":
        return "مادام‌العمر ⚪️"
    if not expiry_date:
        return "نامشخص"
    delta = (datetime.date.fromisoformat(expiry_date) - datetime.date.today()).days
    if delta < 0:
        return "منقضی شده"
    return f"{delta} روز"


def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ============ منوها ============

def main_menu():
    return ReplyKeyboardMarkup([[KeyboardButton(BTN_PANEL), KeyboardButton(BTN_MESSAGE)]], resize_keyboard=True)


def content_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_VIDEO), KeyboardButton(BTN_JOZVE)], [KeyboardButton(BTN_BACK)]], resize_keyboard=True)


def school_pick_menu():
    return ReplyKeyboardMarkup([[KeyboardButton(t)] for t in SCHOOL_BTNS], resize_keyboard=True)


def admin_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(ABTN_CODES), KeyboardButton(ABTN_STUDENTS)],
         [KeyboardButton(ABTN_CONTENT), KeyboardButton(ABTN_BROADCAST)]],
        resize_keyboard=True)


def codes_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CBTN_ACTIVE), KeyboardButton(CBTN_EXPIRED)],
         [KeyboardButton(CBTN_SCHEDULED), KeyboardButton(CBTN_DELETED)],
         [KeyboardButton(CBTN_ADD), KeyboardButton(CBTN_DEL)],
         [KeyboardButton(CBTN_SET_FILE)],
         [KeyboardButton(ABTN_BACK_MAIN)]],
        resize_keyboard=True)


def delcode_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(DBTN_SINGLE), KeyboardButton(DBTN_GROUP)],
         [KeyboardButton(DBTN_ALL)], [KeyboardButton(ABTN_BACK_MAIN)]],
        resize_keyboard=True)


def scope_menu():
    return ReplyKeyboardMarkup([[KeyboardButton(t)] for t in SCOPE_BTNS] + [[KeyboardButton(ABTN_BACK_MAIN)]],
                                resize_keyboard=True)


def major_menu(limited=False):
    btns = MAJOR_BTNS_LIMITED if limited else MAJOR_BTNS
    return ReplyKeyboardMarkup([[KeyboardButton(t)] for t in btns] + [[KeyboardButton(ABTN_BACK_MAIN)]],
                                resize_keyboard=True)


def subtype_menu():
    return ReplyKeyboardMarkup([[KeyboardButton(t)] for t in SUBTYPE_BTNS] + [[KeyboardButton(ABTN_BACK_MAIN)]],
                                resize_keyboard=True)


def target_menu():
    return ReplyKeyboardMarkup([[KeyboardButton(t)] for t in TARGET_BTNS] + [[KeyboardButton(ABTN_BACK_MAIN)]],
                                resize_keyboard=True)


def students_menu():
    return ReplyKeyboardMarkup([[KeyboardButton(SBTN_SEARCH)], [KeyboardButton(ABTN_BACK_MAIN)]], resize_keyboard=True)


def content_placeholder_menu():
    rows = [CONTENT_BTNS[i:i + 2] for i in range(0, len(CONTENT_BTNS), 2)]
    kb = [[KeyboardButton(t) for t in row] for row in rows]
    kb.append([KeyboardButton(ABTN_BACK_MAIN)])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def broadcast_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BBTN_PERSON), KeyboardButton(BBTN_SCHOOL)],
         [KeyboardButton(BBTN_MAJOR), KeyboardButton(BBTN_ALL)],
         [KeyboardButton(ABTN_BACK_MAIN)]],
        resize_keyboard=True)


def admin_edit_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(ABTN_ADD_VIDEO), KeyboardButton(ABTN_ADD_JOZVE)], [KeyboardButton(ABTN_DONE)]],
        resize_keyboard=True)


def get_student(chat_id):
    conn = db()
    row = conn.execute(
        "SELECT telegram_id, code, first_name, last_name, phone, school, message_count FROM students WHERE telegram_id = ?",
        (chat_id,)).fetchone()
    conn.close()
    return row


def get_code_row(code):
    conn = db()
    row = conn.execute(
        "SELECT code, sub_type, school, major, expiry_date, activation_date, is_deleted, video_file_id, video_type, jozve_file_id, jozve_type FROM codes WHERE code = ?",
        (code,)).fetchone()
    conn.close()
    return row


# ============ شروع ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id == ADMIN_CHAT_ID:
        reset_admin_flow()
        await update.message.reply_text("پنل مدیریت 🛠", reply_markup=admin_menu())
        return
    user_state.pop(chat_id, None)
    await update.message.reply_text(
        "به بات گروه آموزشی حد خوش اومدی 🛡\nیکی از گزینه‌های پایین صفحه رو انتخاب کن.",
        reply_markup=main_menu())


# ============ دانش‌آموز: پنل کاربری ============

async def on_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.effective_chat.id, None)
    await update.message.reply_text("منوی اصلی:", reply_markup=main_menu())


async def on_panel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    student = get_student(chat_id)
    if student:
        await update.message.reply_text("به پنلت خوش اومدی 👋 یکی از گزینه‌ها رو انتخاب کن:", reply_markup=content_menu())
    else:
        user_state[chat_id] = "awaiting_code"
        await update.message.reply_text("🪪 کد اختصاصی‌ای که در اختیارت قرار گرفته رو بفرست.")


async def on_message_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state[update.effective_chat.id] = "awaiting_message"
    await update.message.reply_text("✍️ پیامت رو بفرست، مستقیم برای ستاد ارسال میشه.")


async def process_code(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, code: str):
    row = get_code_row(code)
    if not row:
        await update.message.reply_text("❌ کد واردشده معتبر نیست.")
        return

    _, sub_type, _, _, expiry_date, activation_date, is_deleted, *_ = row
    status = get_status(sub_type, expiry_date, activation_date, is_deleted)
    if status == "deleted":
        await update.message.reply_text("❌ این کد دیگه معتبر نیست.")
        return
    if status == "expired":
        await update.message.reply_text("⌛️ اعتبار این کد تموم شده.")
        return
    if status == "scheduled":
        await update.message.reply_text("🕓 این کد هنوز فعال نشده.")
        return

    admin_flow_data = context.user_data
    admin_flow_data["reg_code"] = code
    user_state[chat_id] = "awaiting_fullname"
    await update.message.reply_text("عالی ✅ حالا نام و نام خانوادگیت رو بفرست:")


async def handle_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    parts = text.strip().split(" ", 1)
    context.user_data["reg_first"] = parts[0]
    context.user_data["reg_last"] = parts[1] if len(parts) > 1 else ""
    user_state[chat_id] = "awaiting_phone"
    await update.message.reply_text("شماره تماست رو بفرست:")


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    context.user_data["reg_phone"] = text.strip()
    user_state[chat_id] = "awaiting_school"
    await update.message.reply_text("دبیرستانت کدومه؟", reply_markup=school_pick_menu())


async def finalize_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, school_key: str):
    code = context.user_data.get("reg_code")
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO students (telegram_id, code, first_name, last_name, phone, school, registered_at, message_count) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'), COALESCE((SELECT message_count FROM students WHERE telegram_id=?), 0))",
        (chat_id, code, context.user_data.get("reg_first", ""), context.user_data.get("reg_last", ""),
         context.user_data.get("reg_phone", ""), school_key, chat_id))
    conn.commit()
    conn.close()

    user_state.pop(chat_id, None)
    await update.message.reply_text("🎉 عضویت با موفقیت انجام شد! خوش اومدی 🛡")
    await update.message.reply_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=content_menu())


async def on_school_pick_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if user_state.get(chat_id) != "awaiting_school":
        return
    text = update.message.text
    key = "chamran" if "چمران" in text else ("beheshti" if "بهشتی" in text else "other")
    await finalize_registration(update, context, chat_id, key)


async def deliver_content(chat_id, file_id, ftype, context: ContextTypes.DEFAULT_TYPE):
    if ftype == "video":
        await context.bot.send_video(chat_id=chat_id, video=file_id)
    elif ftype == "photo":
        await context.bot.send_photo(chat_id=chat_id, photo=file_id)
    else:
        await context.bot.send_document(chat_id=chat_id, document=file_id)


async def send_kind(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
    chat_id = update.effective_chat.id
    student = get_student(chat_id)
    if not student:
        await update.message.reply_text("اول باید از «پنل کاربری» کدت رو ثبت کنی.")
        return
    code = student[1]
    row = get_code_row(code)
    if not row:
        await update.message.reply_text("این کد دیگه معتبر نیست.")
        return

    _, sub_type, _, _, expiry_date, activation_date, is_deleted, video_id, video_type, jozve_id, jozve_type = row
    status = get_status(sub_type, expiry_date, activation_date, is_deleted)
    if status != "active":
        labels = {"expired": "⌛️ اعتبار کدت تموم شده.", "deleted": "❌ دسترسیت غیرفعال شده.", "scheduled": "🕓 هنوز فعال نشده."}
        await update.message.reply_text(labels.get(status, "دسترسی نداری."))
        return

    file_id, ftype = (video_id, video_type) if kind == "video" else (jozve_id, jozve_type)
    if not file_id:
        await update.message.reply_text("هنوز فایلی برای این بخش آپلود نشده.")
        return
    await deliver_content(chat_id, file_id, ftype, context)


async def on_video_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_kind(update, context, "video")


async def on_jozve_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_kind(update, context, "jozve")


# ============ دانش‌آموز: ارسال پیام ============

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    user = update.effective_user
    name = user.full_name or user.username or "ناشناس"

    conn = db()
    conn.execute("UPDATE students SET message_count = message_count + 1 WHERE telegram_id = ?", (chat_id,))
    conn.commit()
    conn.close()

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"📩 پیام جدید از: {name}\n(chat_id: {chat_id})")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دیدم", callback_data=f"seen:{chat_id}")]])
    sent = await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=update.message.text, reply_markup=keyboard)
    forward_map[sent.message_id] = chat_id
    await update.message.reply_text("پیامت ارسال شد ✅ منتظر جواب باش.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id == ADMIN_CHAT_ID:
        return

    state = user_state.get(chat_id)
    text = update.message.text

    if state == "awaiting_code":
        user_state.pop(chat_id, None)
        await process_code(update, context, chat_id, text.strip())
    elif state == "awaiting_fullname":
        await handle_fullname(update, context, chat_id, text)
    elif state == "awaiting_phone":
        await handle_phone(update, context, chat_id, text)
    elif state == "awaiting_school":
        return  # با دکمه هندل میشه
    elif state == "awaiting_message":
        user_state.pop(chat_id, None)
        await forward_to_admin(update, context, chat_id)
    else:
        await update.message.reply_text("برای شروع، یکی از گزینه‌های پایین صفحه رو بزن.", reply_markup=main_menu())


async def handle_seen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    student_chat_id = int(query.data.split(":")[1])
    await context.bot.send_message(chat_id=student_chat_id, text="پیامت دیده شد 👁")
    await query.edit_message_reply_markup(reply_markup=None)


# ============ ادمین: منوی اصلی ============

async def admin_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_admin_flow()
    await update.message.reply_text("پنل مدیریت 🛠", reply_markup=admin_menu())


async def admin_open_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_admin_flow()
    await update.message.reply_text("مدیریت کدها:", reply_markup=codes_menu())


async def admin_open_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_admin_flow()
    await update.message.reply_text("لیست دانش‌آموزان:", reply_markup=students_menu())
    await send_students_page(context, update.effective_chat.id, 0)


async def admin_open_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_admin_flow()
    await update.message.reply_text("لیست جزوات/ویدیوها:", reply_markup=content_placeholder_menu())


async def admin_content_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("این بخش به‌زودی فعال میشه.")


async def admin_open_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_admin_flow()
    await update.message.reply_text("پیام همگانی:", reply_markup=broadcast_menu())


# ============ ادمین: کدها ============

async def show_codes_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE, wanted_status: str):
    conn = db()
    rows = conn.execute(
        "SELECT code, sub_type, school, major, expiry_date, activation_date, is_deleted FROM codes").fetchall()
    conn.close()

    lines = []
    for code, sub_type, school, major, expiry_date, activation_date, is_deleted in rows:
        status = get_status(sub_type, expiry_date, activation_date, is_deleted)
        if status != wanted_status:
            continue
        emoji = SUBTYPE_EMOJI.get(sub_type, "⚫️")
        maj = MAJOR_LABEL.get(major, "-")
        sch = SCHOOL_LABEL.get(school, "-")
        lines.append(f"{emoji} {code} | {maj} | {sch}")

    if not lines:
        await update.message.reply_text("موردی یافت نشد.", reply_markup=codes_menu())
        return

    text = "\n".join(lines[:60])
    if len(lines) > 60:
        text += f"\n\n(و {len(lines)-60} مورد دیگر)"
    await update.message.reply_text(text, reply_markup=codes_menu())


async def admin_codes_active(update, context):
    await show_codes_by_status(update, context, "active")


async def admin_codes_expired(update, context):
    await show_codes_by_status(update, context, "expired")


async def admin_codes_scheduled(update, context):
    await show_codes_by_status(update, context, "scheduled")


async def admin_codes_deleted(update, context):
    await show_codes_by_status(update, context, "deleted")


async def admin_add_code_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "ac_count"
    admin_flow["data"] = {}
    await update.message.reply_text("چند تا کد می‌خوای بسازی؟ (فقط عدد)")


async def admin_del_code_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_admin_flow()
    await update.message.reply_text("نوع حذف رو انتخاب کن:", reply_markup=delcode_menu())


async def admin_set_file_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "content_single_code"
    await update.message.reply_text("کدی که می‌خوای فایلش رو تنظیم کنی رو بفرست:")


async def admin_del_single_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "dc_single"
    await update.message.reply_text("کدی که می‌خوای حذف کنی رو بفرست:")


async def admin_del_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "dc_group_pick"
    admin_flow["data"] = {}
    await update.message.reply_text("بر چه اساسی حذف بشه؟", reply_markup=scope_menu())


async def admin_del_all_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "dc_all_confirm1"
await update.message.reply_text(
        "⚠️ این کار تمام کدها و دانش‌آموزها رو حذف می‌کنه و قابل بازگشت نیست.\nبرای ادامه دقیقاً بنویس: تایید")


# ---- انتخاب‌های دکمه‌ای مشترک ----

async def on_scope_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = admin_flow.get("step")
    if step != "ac_scope":
        return
    text = update.message.text
    if "مدرسه" in text:
        admin_flow["data"]["path"] = "school"
        admin_flow["step"] = "ac_school"
        await update.message.reply_text("کدوم مدرسه؟", reply_markup=school_pick_menu())
    else:
        admin_flow["data"]["path"] = "major"
        admin_flow["step"] = "ac_major"
        await update.message.reply_text("کدوم رشته؟", reply_markup=major_menu())


async def on_school_pick_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = admin_flow.get("step")
    text = update.message.text
    school = "chamran" if "چمران" in text else "beheshti"

    if step == "ac_school":
        admin_flow["data"]["school"] = school
        admin_flow["step"] = "ac_major"
        await update.message.reply_text("کدوم رشته؟", reply_markup=major_menu(limited=True))

    elif step == "dc_group_value" and admin_flow["data"].get("basis") == "school":
        conn = db()
        conn.execute("UPDATE codes SET is_deleted=1 WHERE school=?", (school,))
        conn.execute("DELETE FROM students WHERE code IN (SELECT code FROM codes WHERE school=? AND is_deleted=1)", (school,))
        conn.commit()
        conn.close()
        reset_admin_flow()
        await update.message.reply_text(f"همه کدهای مدرسه «{SCHOOL_LABEL[school]}» حذف شدند ✅", reply_markup=codes_menu())

    elif step == "bc_school_pick":
        admin_flow["data"]["school"] = school
        admin_flow["step"] = "bc_school_target_pick"
        await update.message.reply_text("هدف کدوم گروهه؟", reply_markup=target_menu())


async def on_major_pick_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = admin_flow.get("step")
    text = update.message.text
    major = "tajrobi" if "تجربی" in text else ("riazi" if "ریاضی" in text else "ensani")

    if step == "ac_major":
        admin_flow["data"]["major"] = major
        admin_flow["step"] = "ac_subtype"
        await update.message.reply_text("نوع اشتراک؟", reply_markup=subtype_menu())

    elif step == "dc_group_value" and admin_flow["data"].get("basis") == "major":
        conn = db()
        conn.execute("UPDATE codes SET is_deleted=1 WHERE major=?", (major,))
        conn.execute("DELETE FROM students WHERE code IN (SELECT code FROM codes WHERE major=? AND is_deleted=1)", (major,))
        conn.commit()
        conn.close()
        reset_admin_flow()
        await update.message.reply_text(f"همه کدهای رشته «{MAJOR_LABEL[major]}» حذف شدند ✅", reply_markup=codes_menu())

    elif step == "bc_major_pick":
        admin_flow["data"]["major"] = major
        admin_flow["step"] = "bc_major_msg"
        await update.message.reply_text("متن پیام رو بفرست:")


async def on_target_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = admin_flow.get("step")
    if step != "bc_school_target_pick":
        return
    text = update.message.text
    target = "tajrobi" if "تجربی" in text else ("riazi" if "ریاضی" in text else "all")
    admin_flow["data"]["target"] = target
    admin_flow["step"] = "bc_school_msg"
    await update.message.reply_text("متن پیام رو بفرست:")


async def on_subtype_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = admin_flow.get("step")
    if step != "ac_subtype":
        return
    text = update.message.text
    sub_type = "actual" if "Actual" in text else ("tactical" if "Tactical" in text else "scout")
    admin_flow["data"]["sub_type"] = sub_type
    await do_bulk_generate(update, context)


async def do_bulk_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = admin_flow["data"]
    count = d.get("count", 1)
    sub_type = d["sub_type"]
    school = d.get("school")
    major = d.get("major")
    expiry = None if sub_type == "scout" else compute_expiry()
    created_at = today_iso()

    conn = db()
    codes = []
    for _ in range(count):
        c = generate_code()
        while conn.execute("SELECT 1 FROM codes WHERE code=?", (c,)).fetchone():
            c = generate_code()
        conn.execute(
            "INSERT INTO codes (code, sub_type, school, major, created_at, expiry_date, is_deleted) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (c, sub_type, school, major, created_at, expiry))
        codes.append(c)
    conn.commit()
    conn.close()

    reset_admin_flow()
    emoji = SUBTYPE_EMOJI[sub_type]
    text = f"{count} کد ساخته شد {emoji}\n\n" + "\n".join(codes[:60])
    if len(codes) > 60:
        text += f"\n\n(و {len(codes)-60} کد دیگر)"
    await update.message.reply_text(text, reply_markup=codes_menu())


# ============ ادمین: تنظیم فایل و آپلود ============

async def admin_add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = admin_flow.get("data", {}).get("edit_code")
    if not code:
        return
    admin_upload_state["pending"] = ("video", code)
    await update.message.reply_text("فایل ویدیو رو الان بفرست.")


async def admin_add_jozve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = admin_flow.get("data", {}).get("edit_code")
    if not code:
        return
    admin_upload_state["pending"] = ("jozve", code)
    await update.message.reply_text("فایل جزوه رو الان بفرست.")


async def admin_done_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = admin_flow.get("data", {}).get("edit_code")
    reset_admin_flow()
    if code:
        await update.message.reply_text(f"فایل‌های کد «{code}» ذخیره شد ✅", reply_markup=codes_menu())
    else:
        await update.message.reply_text("پنل مدیریت 🛠", reply_markup=admin_menu())


async def handle_admin_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = admin_upload_state.get("pending")
    if not pending:
        return
    kind, code = pending

    if update.message.video:
        file_id, ftype = update.message.video.file_id, "video"
    elif update.message.document:
        file_id, ftype = update.message.document.file_id, "document"
    elif update.message.photo:
        file_id, ftype = update.message.photo[-1].file_id, "photo"
    else:
        await update.message.reply_text("این نوع فایل پشتیبانی نمیشه.")
        return

    col_file = "video_file_id" if kind == "video" else "jozve_file_id"
    col_type = "video_type" if kind == "video" else "jozve_type"
    conn = db()
    conn.execute(f"UPDATE codes SET {col_file}=?, {col_type}=? WHERE code=?", (file_id, ftype, code))
    conn.commit()
    conn.close()

    admin_upload_state["pending"] = None
    label = "ویدیو" if kind == "video" else "جزوه"
    await update.message.reply_text(f"فایل {label} ثبت شد ✅", reply_markup=admin_edit_menu())


# ============ ادمین: دانش‌آموزان (لیست + پروفایل) ============

PER_PAGE = 10


async def send_students_page(context, chat_id, page, message_id=None):
    search = admin_flow.get("data", {}).get("search")
    conn = db()
    if search:
        rows = conn.execute(
            "SELECT s.telegram_id, s.first_name, s.last_name, s.code, c.sub_type FROM students s "
            "LEFT JOIN codes c ON s.code=c.code "
            "WHERE s.first_name LIKE ? OR s.last_name LIKE ? OR s.code LIKE ? ORDER BY s.registered_at DESC",
            (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        rows = conn.execute(
            "SELECT s.telegram_id, s.first_name, s.last_name, s.code, c.sub_type FROM students s "
            "LEFT JOIN codes c ON s.code=c.code ORDER BY s.registered_at DESC").fetchall()
    conn.close()

    total = len(rows)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    chunk = rows[page * PER_PAGE: (page + 1) * PER_PAGE]

    kb = []
    for tid, fn, ln, code, sub in chunk:
        emoji = SUBTYPE_EMOJI.get(sub, "⚫️")
        name = f"{fn or ''} {ln or ''}".strip() or "بدون‌نام"
        kb.append([InlineKeyboardButton(f"{emoji} {name} | {code}", callback_data=f"profile:{tid}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"studpage:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"studpage:{page+1}"))
    kb.append(nav)

    text = f"👥 {total} دانش‌آموز" + (f" (جستجو: {search})" if search else "")
    markup = InlineKeyboardMarkup(kb)

    if message_id:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def on_studpage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[1])
    await send_students_page(context, query.message.chat_id, page, message_id=query.message.message_id)


async def on_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def admin_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "search_students"
    await update.message.reply_text("اسم یا کد رو بفرست:")


async def on_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split(":")[1])

    conn = db()
    s = conn.execute(
        "SELECT first_name, last_name, phone, school, code, message_count FROM students WHERE telegram_id=?",
        (tid,)).fetchone()
    if not s:
        conn.close()
        await query.message.reply_text("پیدا نشد.")
        return
    fn, ln, phone, school, code, msg_count = s
    c = conn.execute("SELECT sub_type, expiry_date FROM codes WHERE code=?", (code,)).fetchone()
    conn.close()

    sub_type, expiry_date = c if c else (None, None)
    sub_label = SUBTYPE_LABEL.get(sub_type, "-")
    remaining = remaining_text(sub_type, expiry_date) if sub_type else "-"
    school_label = SCHOOL_LABEL.get(school, school or "-")

    text = (
        f"👤 {fn or ''} {ln or ''}\n"
        f"📞 {phone or '-'}\n"
        f"🏫 {school_label}\n"
        f"🔑 کد: {code}\n"
        f"🎖 اشتراک: {sub_label}\n"
        f"⏳ باقی‌مانده: {remaining}\n"
        f"✉️ پیام‌های ارسالی: {msg_count}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ ارسال پیام مستقیم", callback_data=f"paction:msg:{tid}")],
        [InlineKeyboardButton("🛠 پیام عیب‌یابی", callback_data=f"paction:trouble:{tid}")],
        [InlineKeyboardButton("📊 نظرسنجی", callback_data=f"paction:survey:{tid}")],
        [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="studpage:0")]
    ])
    await query.message.reply_text(text, reply_markup=kb)


async def on_profile_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, action, tid_str = query.data.split(":")
    tid = int(tid_str)

    if action == "msg":
        admin_flow["step"] = "awaiting_direct_message"
        admin_flow["data"]["target"] = tid
        await query.message.reply_text("متن پیام رو بفرست:")

    elif action == "trouble":
        await context.bot.send_message(
            chat_id=tid,
            text="سلام 👋 اگه تو استفاده از بات مشکلی داری (باز نشدن فایل، اجرا نشدن ویدیو و...) این‌ها رو امتحان کن:\n"
                 "۱. اپلیکیشن تلگرام رو آپدیت کن\n۲. بات رو با /start دوباره شروع کن\n۳. اتصال اینترنتت رو چک کن\n\n"
                 "اگه بازم حل نشد، از «ارسال پیام» بهمون بگو دقیقاً چه مشکلی داری."
        )
        await query.message.reply_text("پیام عیب‌یابی ارسال شد ✅")

    elif action == "survey":
        await context.bot.send_poll(
            chat_id=tid,
            question="چقدر از محتوای ارائه‌شده راضی هستی؟",
            options=["خیلی راضی‌ام", "راضی‌ام", "معمولیه", "راضی نیستم"],
            is_anonymous=False
        )
        await query.message.reply_text("نظرسنجی ارسال شد ✅")


# ============ ادمین: پیام همگانی ============

async def bc_person_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "bc_person"
    admin_flow["data"] = {}
    await update.message.reply_text("کد یا آیدی عددی دانش‌آموز رو بفرست:")


async def bc_school_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "bc_school_pick"
    admin_flow["data"] = {}
    await update.message.reply_text("کدوم مدرسه؟", reply_markup=school_pick_menu())


async def bc_major_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "bc_major_pick"
    admin_flow["data"] = {}
    await update.message.reply_text("کدوم رشته؟", reply_markup=major_menu())


async def bc_all_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "bc_all_msg"
    admin_flow["data"] = {}
    await update.message.reply_text("متن پیام همگانی رو بفرست:")


async def send_broadcast(context, chat_ids, text):
    sent = 0
    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=cid, text=text)
            sent += 1
        except Exception:
            pass
    return sent


# ============ ادمین: مسیر متن‌های آزاد ============

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        replied_id = update.message.reply_to_message.message_id
        if replied_id in forward_map:
            student_chat_id = forward_map[replied_id]
            await context.bot.send_message(chat_id=student_chat_id, text=update.message.text)
            return

    step = admin_flow.get("step")
    text = update.message.text.strip()

    if step == "ac_count":
        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text("یه عدد معتبر بفرست.")
            return
        admin_flow["data"]["count"] = min(int(text), 500)
        admin_flow["step"] = "ac_scope"
        await update.message.reply_text("بر چه اساسی؟", reply_markup=scope_menu())

    elif step == "dc_single":
        conn = db()
        conn.execute("UPDATE codes SET is_deleted=1 WHERE code=?", (text,))
        conn.execute("DELETE FROM students WHERE code=?", (text,))
        conn.commit()
        conn.close()
        reset_admin_flow()
        await update.message.reply_text(f"کد «{text}» حذف شد ✅", reply_markup=codes_menu())

    elif step == "dc_group_pick":
        if "مدرسه" in text:
            admin_flow["data"]["basis"] = "school"
            admin_flow["step"] = "dc_group_value"
            await update.message.reply_text("کدوم مدرسه؟", reply_markup=school_pick_menu())
        elif "رشته" in text:
            admin_flow["data"]["basis"] = "major"
            admin_flow["step"] = "dc_group_value"
            await update.message.reply_text("کدوم رشته؟", reply_markup=major_menu())
        else:
            await update.message.reply_text("یکی از گزینه‌های پایین صفحه رو بزن.")

    elif step == "dc_all_confirm1":
        if text == "تایید":
            conn = db()
            conn.execute("UPDATE codes SET is_deleted=1")
            conn.execute("DELETE FROM students")
            conn.commit()
            conn.close()
            reset_admin_flow()
            await update.message.reply_text("همه کدها و دانش‌آموزها حذف شدند ✅", reply_markup=codes_menu())
        else:
            reset_admin_flow()
            await update.message.reply_text("لغو شد.", reply_markup=codes_menu())

    elif step == "content_single_code":
        code = text
        row = get_code_row(code)
        if not row:
            await update.message.reply_text("همچین کدی وجود نداره.")
            return
        admin_flow["step"] = "editing_code"
        admin_flow["data"]["edit_code"] = code
        await update.message.reply_text(f"کد «{code}» انتخاب شد. یکی از گزینه‌ها رو بزن:", reply_markup=admin_edit_menu())

    elif step == "search_students":
        admin_flow["data"]["search"] = text
        admin_flow["step"] = None
        await update.message.reply_text(f"نتایج جستجو برای «{text}»:")
        await send_students_page(context, update.effective_chat.id, 0)

    elif step == "awaiting_direct_message":
        target = admin_flow["data"].get("target")
        if target:
            await context.bot.send_message(chat_id=target, text=text)
            await update.message.reply_text("پیام ارسال شد ✅")
        reset_admin_flow()

    elif step == "bc_person":
        conn = db()
        row = conn.execute("SELECT telegram_id FROM students WHERE code=? OR telegram_id=?", (text, text)).fetchone()
        conn.close()
        if not row:
            await update.message.reply_text("پیدا نشد. دوباره امتحان کن یا کد/آیدی معتبر بفرست.")
            return
        admin_flow["data"]["target"] = row[0]
        admin_flow["step"] = "bc_person_msg"
        await update.message.reply_text("متن پیام رو بفرست:")

    elif step == "bc_person_msg":
        target = admin_flow["data"]["target"]
        await context.bot.send_message(chat_id=target, text=text)
        reset_admin_flow()
        await update.message.reply_text("پیام ارسال شد ✅", reply_markup=broadcast_menu())

    elif step == "bc_school_msg":
        d = admin_flow["data"]
        conn = db()
        if d["target"] == "all":
            rows = conn.execute(
                "SELECT s.telegram_id FROM students s JOIN codes c ON s.code=c.code WHERE c.school=?",
                (d["school"],)).fetchall()
        else:
            rows = conn.execute(
                "SELECT s.telegram_id FROM students s JOIN codes c ON s.code=c.code WHERE c.school=? AND c.major=?",
                (d["school"], d["target"])).fetchall()
        conn.close()
        sent = await send_broadcast(context, [r[0] for r in rows], text)
        reset_admin_flow()
        await update.message.reply_text(f"پیام برای {sent} نفر ارسال شد ✅", reply_markup=broadcast_menu())

    elif step == "bc_major_msg":
        d = admin_flow["data"]
        conn = db()
        rows = conn.execute(
            "SELECT s.telegram_id FROM students s JOIN codes c ON s.code=c.code WHERE c.major=?",
            (d["major"],)).fetchall()
        conn.close()
        sent = await send_broadcast(context, [r[0] for r in rows], text)
        reset_admin_flow()
        await update.message.reply_text(f"پیام برای {sent} نفر ارسال شد ✅", reply_markup=broadcast_menu())

    elif step == "bc_all_msg":
        conn = db()
        rows = conn.execute("SELECT telegram_id FROM students").fetchall()
        conn.close()
        sent = await send_broadcast(context, [r[0] for r in rows], text)
        reset_admin_flow()
        await update.message.reply_text(f"پیام برای {sent} نفر ارسال شد ✅", reply_markup=broadcast_menu())

    else:
        await update.message.reply_text("یکی از گزینه‌های پایین صفحه رو بزن.", reply_markup=admin_menu())


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_seen, pattern="^seen:"))
    app.add_handler(CallbackQueryHandler(on_studpage, pattern="^studpage:"))
    app.add_handler(CallbackQueryHandler(on_noop, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(on_profile, pattern="^profile:"))
    app.add_handler(CallbackQueryHandler(on_profile_action, pattern="^paction:"))

    admin_only = filters.User(ADMIN_CHAT_ID)

    # منوی اصلی ادمین
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_CODES}$") & admin_only, admin_open_codes))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_STUDENTS}$") & admin_only, admin_open_students))
    app.add_handler(CallbackQueryHandler(on_studpage, pattern="^studpage:"))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_BROADCAST}$") & admin_only, admin_open_broadcast))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_BACK_MAIN}$") & admin_only, admin_back_main))

    # زیرمنوی کدها
    app.add_handler(MessageHandler(filters.Regex(f"^{CBTN_ACTIVE}$") & admin_only, admin_codes_active))
    app.add_handler(MessageHandler(filters.Regex(f"^{CBTN_EXPIRED}$") & admin_only, admin_codes_expired))
    app.add_handler(MessageHandler(filters.Regex(f"^{CBTN_SCHEDULED}$") & admin_only, admin_codes_scheduled))
    app.add_handler(MessageHandler(filters.Regex(f"^{CBTN_DELETED}$") & admin_only, admin_codes_deleted))
    app.add_handler(MessageHandler(filters.Regex(f"^{CBTN_ADD}$") & admin_only, admin_add_code_start))
    app.add_handler(MessageHandler(filters.Regex(f"^{CBTN_DEL}$") & admin_only, admin_del_code_menu))
    app.add_handler(MessageHandler(filters.Regex(f"^{CBTN_SET_FILE}$") & admin_only, admin_set_file_start))

    app.add_handler(MessageHandler(filters.Regex(f"^{DBTN_SINGLE}$") & admin_only, admin_del_single_start))
    app.add_handler(MessageHandler(filters.Regex(f"^{DBTN_GROUP}$") & admin_only, admin_del_group_start))
    app.add_handler(MessageHandler(filters.Regex(f"^{DBTN_ALL}$") & admin_only, admin_del_all_start))

    # انتخاب‌های دکمه‌ای مشترک (اسکوپ/مدرسه/رشته/نوع اشتراک/هدف)
    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(SCOPE_BTNS) + ")$") & admin_only, on_scope_pick))
    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(SCHOOL_BTNS[:2]) + ")$") & admin_only, on_school_pick_admin))
    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(MAJOR_BTNS) + ")$") & admin_only, on_major_pick_admin))
    app.add_handler(MessageHandler(filters.Regex("^🌐 همه$") & admin_only, on_target_pick))
    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(SUBTYPE_BTNS) + ")$") & admin_only, on_subtype_pick))

    # ویرایش فایل یک کد
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_ADD_VIDEO}$") & admin_only, admin_add_video))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_ADD_JOZVE}$") & admin_only, admin_add_jozve))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_DONE}$") & admin_only, admin_done_edit))

    # دانش‌آموزان
    app.add_handler(MessageHandler(filters.Regex(f"^{SBTN_SEARCH}$") & admin_only, admin_search_start))

    # محتوا (placeholder)
    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(CONTENT_BTNS) + ")$") & admin_only, admin_content_placeholder))

    # پیام همگانی
    app.add_handler(MessageHandler(filters.Regex(f"^{BBTN_PERSON}$") & admin_only, bc_person_start))
    app.add_handler(MessageHandler(filters.Regex(f"^{BBTN_SCHOOL}$") & admin_only, bc_school_start))
    app.add_handler(MessageHandler(filters.Regex(f"^{BBTN_MAJOR}$") & admin_only, bc_major_start))
    app.add_handler(MessageHandler(filters.Regex(f"^{BBTN_ALL}$") & admin_only, bc_all_start))

    # آپلود فایل ادمین
    app.add_handler(MessageHandler((filters.VIDEO | filters.Document.ALL | filters.PHOTO) & admin_only, handle_admin_file))

    # متن آزاد ادمین
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & admin_only, handle_admin_text))

    # ---- دانش‌آموز ----
    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(SCHOOL_BTNS) + ")$"), on_school_pick_student))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_PANEL}$"), on_panel_button))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_MESSAGE}$"), on_message_button))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_VIDEO}$"), on_video_button))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_JOZVE}$"), on_jozve_button))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_BACK}$"), on_back_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("بات روشن شد...")
    app.run_polling()


if __name__ == "__main__":
    main()
