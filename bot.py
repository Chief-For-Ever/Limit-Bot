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

# ============ تنظیمات (اینا رو پر کن) ============
BOT_TOKEN = "8753659672:AAH0tHsxH3YAG6Ogf8aJUTzGfIzS5e6gSow"          # از BotFather گرفتی
ADMIN_CHAT_ID = 1252988484             # آیدی عددی تلگرام خودت
# ==================================================

logging.basicConfig(level=logging.INFO)

BTN_PANEL = "🪪 پنل کاربری"
BTN_MESSAGE = "💬 ارسال پیام"
BTN_VIDEO = "🎥 ویدیو"
BTN_JOZVE = "📄 جزوه"
BTN_BACK = "🔙 بازگشت"

# وضعیت فعلی هر کاربر عادی: None / 'awaiting_code' / 'awaiting_message'
user_state = {}

# وضعیت آپلود ادمین: None یا ('video'|'jozve', code)
admin_upload_state = {"pending": None}

# نگاشت: آیدی پیام فوروارد شده تو چت ادمین -> chat_id دانش‌آموز
forward_map = {}


def init_db():
    conn = sqlite3.connect("students.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            telegram_id INTEGER PRIMARY KEY,
            code TEXT,
            registered_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            video_file_id TEXT,
            video_type TEXT,
            jozve_file_id TEXT,
            jozve_type TEXT
        )
    """)
    conn.commit()
    conn.close()


def main_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text=BTN_PANEL), KeyboardButton(text=BTN_MESSAGE)]],
        resize_keyboard=True
    )


def content_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text=BTN_VIDEO), KeyboardButton(text=BTN_JOZVE)],
         [KeyboardButton(text=BTN_BACK)]],
        resize_keyboard=True
    )


def get_student_code(chat_id):
    conn = sqlite3.connect("students.db")
    row = conn.execute("SELECT code FROM students WHERE telegram_id = ?", (chat_id,)).fetchone()
    conn.close()
    return row[0] if row else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.effective_chat.id, None)
    await update.message.reply_text(
        "به بات گروه آموزشی حد خوش اومدی 🛡\n"
        "یکی از گزینه‌های پایین صفحه رو انتخاب کن.",
        reply_markup=main_menu()
    )


async def on_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.effective_chat.id, None)
    await update.message.reply_text("منوی اصلی:", reply_markup=main_menu())


async def on_panel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    code = get_student_code(chat_id)

    if code:
        await update.message.reply_text(
            "به پنلت خوش اومدی 👋 یکی از گزینه‌ها رو انتخاب کن:",
            reply_markup=content_menu()
        )
    else:
        user_state[chat_id] = "awaiting_code"
        await update.message.reply_text(
            "🪪 کد اختصاصی‌ای که در اختیارت قرار گرفته رو بفرست."
        )


async def on_message_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = "awaiting_message"
    await update.message.reply_text(
        "✍️ پیامت رو بفرست، مستقیم برای ستاد ارسال میشه."
    )


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
    await update.message.reply_text(
        "یکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=content_menu()
    )


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


async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    user = update.effective_user
    name = user.full_name or user.username or "ناشناس"

    caption = f"📩 پیام جدید از: {name}\n(chat_id: {chat_id})"
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=caption)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ دیدم", callback_data=f"seen:{chat_id}")]
    ])
    sent = await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=update.message.text,
        reply_markup=keyboard
    )

    forward_map[sent.message_id] = chat_id
    await update.message.reply_text("پیامت ارسال شد ✅ منتظر جواب باش.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id == ADMIN_CHAT_ID and update.message.reply_to_message:
        replied_id = update.message.reply_to_message.message_id
        if replied_id in forward_map:
            student_chat_id = forward_map[replied_id]
            await context.bot.send_message(chat_id=student_chat_id, text=update.message.text)
            return

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
        await update.message.reply_text(
            "برای شروع، یکی از گزینه‌های پایین صفحه رو بزن.",
            reply_markup=main_menu()
        )


async def handle_seen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    student_chat_id = int(query.data.split(":")[1])
    await context.bot.send_message(chat_id=student_chat_id, text="پیامت دیده شد 👁")
    await query.edit_message_reply_markup(reply_markup=None)


# ============ دستورات ادمین ============

async def add_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرمت: /addcode CODE  — بعدش خودش پشت سر هم ویدیو و جزوه رو ازت می‌خواد."""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("فرمت درست:\n/addcode CODE")
        return
    code = context.args[0]
    conn = sqlite3.connect("students.db")
    conn.execute("INSERT OR IGNORE INTO codes (code) VALUES (?)", (code,))
    conn.commit()
    conn.close()

    admin_upload_state["pending"] = ("video", code)
    await update.message.reply_text(
        f"کد «{code}» ساخته شد ✅\nحالا فایل ویدیوی مربوطه رو بفرست."
    )


async def set_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("فرمت درست:\n/setvideo CODE")
        return
    code = context.args[0]
    admin_upload_state["pending"] = ("video", code)
    await update.message.reply_text(f"فایل ویدیوی مربوط به کد «{code}» رو الان بفرست.")


async def set_jozve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("فرمت درست:\n/setjozve CODE")
        return
    code = context.args[0]
    admin_upload_state["pending"] = ("jozve", code)
    await update.message.reply_text(f"فایل جزوه‌ی مربوط به کد «{code}» رو الان بفرست.")


async def handle_admin_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
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

    if kind == "video":
        admin_upload_state["pending"] = ("jozve", code)
        await update.message.reply_text("فایل ویدیو ثبت شد ✅\nحالا فایل جزوه رو بفرست.")
    else:
        admin_upload_state["pending"] = None
        await update.message.reply_text(f"فایل جزوه هم ثبت شد ✅\nکد «{code}» کامل آماده‌ست.")


async def del_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرمت: /delcode CODE"""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("فرمت درست:\n/delcode CODE")
        return
    code = context.args[0]
    conn = sqlite3.connect("students.db")
    conn.execute("DELETE FROM codes WHERE code = ?", (code,))
    conn.execute("DELETE FROM students WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"کد «{code}» و دسترسی دانش‌آموزهای مرتبط باهاش حذف شد ✅")


async def del_all_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف همه کدها و همه دانش‌آموزهای ثبت‌شده."""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    conn = sqlite3.connect("students.db")
    conn.execute("DELETE FROM codes")
    conn.execute("DELETE FROM students")
    conn.commit()
    conn.close()
    await update.message.reply_text("همه کدها و دانش‌آموزهای ثبت‌شده حذف شدند ✅")


async def list_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    conn = sqlite3.connect("students.db")
    rows = conn.execute("SELECT code, video_file_id, jozve_file_id FROM codes").fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("هیچ کدی ثبت نشده.")
        return
    text = "\n".join([f"• {c} — 🎥{'✓' if v else '✗'} 📄{'✓' if j else '✗'}" for c, v, j in rows])
    await update.message.reply_text(text)


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcode", add_code))
    app.add_handler(CommandHandler("setvideo", set_video))
    app.add_handler(CommandHandler("setjozve", set_jozve))
    app.add_handler(CommandHandler("delcode", del_code))
    app.add_handler(CommandHandler("delallcodes", del_all_codes))
    app.add_handler(CommandHandler("codes", list_codes))
    app.add_handler(CallbackQueryHandler(handle_seen, pattern="^seen:"))

    app.add_handler(MessageHandler(
        (filters.VIDEO | filters.Document.ALL | filters.PHOTO) & filters.User(ADMIN_CHAT_ID),
        handle_admin_file
    ))

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
