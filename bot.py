import logging
import sqlite3
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
# ==================================

logging.basicConfig(level=logging.INFO)

# ---------- دکمه‌های دانش‌آموز ----------
BTN_PANEL = "🪪 پنل کاربری"
BTN_MESSAGE = "💬 ارسال پیام"
BTN_VIDEO = "🎥 ویدیو"
BTN_JOZVE = "📄 جزوه"
BTN_BACK = "🔙 بازگشت"

# ---------- دکمه‌های ادمین ----------
ABTN_NEW = "➕ کد جدید"
ABTN_LIST = "📋 لیست کدها"
ABTN_DEL_ONE = "🗑 حذف یک کد"
ABTN_DEL_ALL = "🗑 حذف همه کدها"
ABTN_ADD_VIDEO = "🎥 افزودن ویدیو"
ABTN_ADD_JOZVE = "📄 افزودن جزوه"
ABTN_DONE = "✅ اتمام و بازگشت"

user_state = {}                              # دانش‌آموزها: None / awaiting_code / awaiting_message
admin_flow = {"step": None, "code": None}     # ادمین: مراحل ساخت/حذف کد
admin_upload_state = {"pending": None}        # ('video'|'jozve', code)
forward_map = {}                              # message_id فوروارد شده -> chat_id دانش‌آموز


def init_db():
    conn = sqlite3.connect("students.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS students (
        telegram_id INTEGER PRIMARY KEY, code TEXT, registered_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS codes (
        code TEXT PRIMARY KEY, video_file_id TEXT, video_type TEXT,
        jozve_file_id TEXT, jozve_type TEXT)""")
    conn.commit()
    conn.close()


def main_menu():
    return ReplyKeyboardMarkup([[KeyboardButton(BTN_PANEL), KeyboardButton(BTN_MESSAGE)]], resize_keyboard=True)


def content_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_VIDEO), KeyboardButton(BTN_JOZVE)], [KeyboardButton(BTN_BACK)]],
        resize_keyboard=True
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(ABTN_NEW), KeyboardButton(ABTN_LIST)],
         [KeyboardButton(ABTN_DEL_ONE), KeyboardButton(ABTN_DEL_ALL)]],
        resize_keyboard=True
    )


def admin_edit_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(ABTN_ADD_VIDEO), KeyboardButton(ABTN_ADD_JOZVE)], [KeyboardButton(ABTN_DONE)]],
        resize_keyboard=True
    )


def get_student_code(chat_id):
    conn = sqlite3.connect("students.db")
    row = conn.execute("SELECT code FROM students WHERE telegram_id = ?", (chat_id,)).fetchone()
    conn.close()
    return row[0] if row else None


# ============ شروع ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id == ADMIN_CHAT_ID:
        admin_flow["step"] = None
        admin_flow["code"] = None
        await update.message.reply_text("پنل مدیریت 🛠", reply_markup=admin_menu())
        return

    user_state.pop(chat_id, None)
    await update.message.reply_text(
        "به بات گروه آموزشی حد خوش اومدی 🛡\nیکی از گزینه‌های پایین صفحه رو انتخاب کن.",
        reply_markup=main_menu()
    )


# ============ دانش‌آموز: پنل کاربری ============

async def on_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.effective_chat.id, None)
    await update.message.reply_text("منوی اصلی:", reply_markup=main_menu())


async def on_panel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    code = get_student_code(chat_id)
    if code:
        await update.message.reply_text("به پنلت خوش اومدی 👋 یکی از گزینه‌ها رو انتخاب کن:", reply_markup=content_menu())
    else:
        user_state[chat_id] = "awaiting_code"
        await update.message.reply_text("🪪 کد اختصاصی‌ای که در اختیارت قرار گرفته رو بفرست.")


async def on_message_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = "awaiting_message"
    await update.message.reply_text("✍️ پیامت رو بفرست، مستقیم برای ستاد ارسال میشه.")


async def process_code(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, code: str):
    conn = sqlite3.connect("students.db")
    cur = conn.cursor()
    cur.execute("SELECT code FROM codes WHERE code = ?", (code,))
    row = cur.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("❌ کد واردشده معتبر نیست.")
        return

    cur.execute(
        "INSERT OR REPLACE INTO students (telegram_id, code, registered_at) VALUES (?, ?, datetime('now'))",
        (chat_id, code)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("🎉 عضویت با موفقیت انجام شد! خوش اومدی 🛡")
    await update.message.reply_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=content_menu())


async def deliver_content(chat_id, file_id, ftype, context: ContextTypes.DEFAULT_TYPE):
    if ftype == "video":
        await context.bot.send_video(chat_id=chat_id, video=file_id)
    elif ftype == "photo":
        await context.bot.send_photo(chat_id=chat_id, photo=file_id)
    else:
        await context.bot.send_document(chat_id=chat_id, document=file_id)


async def send_kind(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
    chat_id = update.effective_chat.id
    code = get_student_code(chat_id)
    if not code:
        await update.message.reply_text("اول باید از «پنل کاربری» کدت رو ثبت کنی.")
        return

    conn = sqlite3.connect("students.db")
    row = conn.execute(
        "SELECT video_file_id, video_type, jozve_file_id, jozve_type FROM codes WHERE code = ?", (code,)
    ).fetchone()
    conn.close()
    if not row:
        await update.message.reply_text("این کد دیگه معتبر نیست.")
        return

    video_id, video_type, jozve_id, jozve_type = row
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
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"📩 پیام جدید از: {name}\n(chat_id: {chat_id})")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دیدم", callback_data=f"seen:{chat_id}")]])
    sent = await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=update.message.text, reply_markup=keyboard)
    forward_map[sent.message_id] = chat_id
    await update.message.reply_text("پیامت ارسال شد ✅ منتظر جواب باش.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط برای دانش‌آموزها (پیام‌های متنی ادمین قبل از این هندل میشه)."""
    chat_id = update.effective_chat.id
    if chat_id == ADMIN_CHAT_ID:
        return

    state = user_state.get(chat_id)
    if state == "awaiting_code":
        user_state.pop(chat_id, None)
        await process_code(update, context, chat_id, update.message.text.strip())
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


# ============ پنل مدیریت (فقط ادمین) ============

async def admin_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "awaiting_new_code_name"
    await update.message.reply_text("اسم/کد جدید رو بفرست (مثلاً BIO101):")


async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("students.db")
    codes_rows = conn.execute("SELECT code, video_file_id, jozve_file_id FROM codes").fetchall()
    counts = dict(conn.execute("SELECT code, COUNT(*) FROM students GROUP BY code").fetchall())
    conn.close()

    if not codes_rows:
        await update.message.reply_text("هنوز کدی ثبت نشده.", reply_markup=admin_menu())
        return

    lines = []
    for code, v, j in codes_rows:
        cnt = counts.get(code, 0)
        lines.append(f"• {code} — 🎥{'✓' if v else '✗'} 📄{'✓' if j else '✗'} — 👥{cnt} دانش‌آموز")
    await update.message.reply_text("\n".join(lines), reply_markup=admin_menu())


async def admin_del_one(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "awaiting_delete_code"
    await update.message.reply_text("اسم کدی که می‌خوای حذف کنی رو بفرست:")


async def admin_del_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_flow["step"] = "awaiting_delete_all_confirm"
    await update.message.reply_text("مطمئنی می‌خوای همه کدها حذف بشن؟ برای تایید دقیقاً بنویس: بله")


async def admin_add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = admin_flow.get("code")
    if not code:
        await update.message.reply_text("اول از «➕ کد جدید» یه کد بساز.", reply_markup=admin_menu())
        return
    admin_upload_state["pending"] = ("video", code)
    await update.message.reply_text(f"فایل ویدیوی کد «{code}» رو الان بفرست.")


async def admin_add_jozve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = admin_flow.get("code")
    if not code:
        await update.message.reply_text("اول از «➕ کد جدید» یه کد بساز.", reply_markup=admin_menu())
        return
    admin_upload_state["pending"] = ("jozve", code)
    await update.message.reply_text(f"فایل جزوه‌ی کد «{code}» رو الان بفرست.")


async def admin_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = admin_flow.get("code")
    admin_flow["code"] = None
    admin_flow["step"] = None
    if code:
        await update.message.reply_text(f"کد «{code}» ذخیره شد ✅", reply_markup=admin_menu())
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
        await update.message.reply_text("این نوع فایل پشتیبانی نمیشه، یه ویدیو/عکس/سند بفرست.")
        return

    column_file = "video_file_id" if kind == "video" else "jozve_file_id"
    column_type = "video_type" if kind == "video" else "jozve_type"

    conn = sqlite3.connect("students.db")
    conn.execute(f"UPDATE codes SET {column_file} = ?, {column_type} = ? WHERE code = ?", (file_id, ftype, code))
    conn.commit()
    conn.close()

    admin_upload_state["pending"] = None
    label = "ویدیو" if kind == "video" else "جزوه"
    await update.message.reply_text(f"فایل {label} ثبت شد ✅", reply_markup=admin_edit_menu())


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیام‌های متنی آزاد ادمین (پاسخ به مراحل، یا ریپلای به پیام دانش‌آموز)."""
    if update.message.reply_to_message:
        replied_id = update.message.reply_to_message.message_id
        if replied_id in forward_map:
            student_chat_id = forward_map[replied_id]
            await context.bot.send_message(chat_id=student_chat_id, text=update.message.text)
            return

    step = admin_flow.get("step")
    text = update.message.text.strip()

    if step == "awaiting_new_code_name":
        conn = sqlite3.connect("students.db")
        conn.execute("INSERT OR IGNORE INTO codes (code) VALUES (?)", (text,))
        conn.commit()
        conn.close()
        admin_flow["step"] = "editing_code"
        admin_flow["code"] = text
        await update.message.reply_text(f"کد «{text}» ساخته شد ✅\nحالا فایل‌ها رو اضافه کن:", reply_markup=admin_edit_menu())

    elif step == "awaiting_delete_code":
        conn = sqlite3.connect("students.db")
        conn.execute("DELETE FROM codes WHERE code = ?", (text,))
        conn.execute("DELETE FROM students WHERE code = ?", (text,))
        conn.commit()
        conn.close()
        admin_flow["step"] = None
        await update.message.reply_text(f"کد «{text}» و دسترسی دانش‌آموزهای مرتبط حذف شد ✅", reply_markup=admin_menu())

    elif step == "awaiting_delete_all_confirm":
        admin_flow["step"] = None
        if text == "بله":
            conn = sqlite3.connect("students.db")
            conn.execute("DELETE FROM codes")
            conn.execute("DELETE FROM students")
            conn.commit()
            conn.close()
            await update.message.reply_text("همه کدها و دانش‌آموزها حذف شدند ✅", reply_markup=admin_menu())
        else:
            await update.message.reply_text("لغو شد.", reply_markup=admin_menu())

    else:
        await update.message.reply_text("یکی از گزینه‌های پایین صفحه رو بزن.", reply_markup=admin_menu())


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_seen, pattern="^seen:"))

    # --- دکمه‌های پنل مدیریت (فقط ادمین) ---
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_NEW}$") & filters.User(ADMIN_CHAT_ID), admin_new))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_LIST}$") & filters.User(ADMIN_CHAT_ID), admin_list))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_DEL_ONE}$") & filters.User(ADMIN_CHAT_ID), admin_del_one))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_DEL_ALL}$") & filters.User(ADMIN_CHAT_ID), admin_del_all))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_ADD_VIDEO}$") & filters.User(ADMIN_CHAT_ID), admin_add_video))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_ADD_JOZVE}$") & filters.User(ADMIN_CHAT_ID), admin_add_jozve))
    app.add_handler(MessageHandler(filters.Regex(f"^{ABTN_DONE}$") & filters.User(ADMIN_CHAT_ID), admin_done))

    # آپلود فایل توسط ادمین
    app.add_handler(MessageHandler(
        (filters.VIDEO | filters.Document.ALL | filters.PHOTO) & filters.User(ADMIN_CHAT_ID),
        handle_admin_file
    ))

    # هر متن دیگه از طرف ادمین
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_CHAT_ID), handle_admin_text))

    # --- دکمه‌های دانش‌آموز ---
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
