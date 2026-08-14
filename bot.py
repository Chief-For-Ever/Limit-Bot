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

# وضعیت فعلی هر کاربر: None / 'awaiting_code' / 'awaiting_message'
user_state = {}

# نگاشت: آیدی پیام فوروارد شده تو چت ادمین -> chat_id دانش‌آموز
forward_map = {}


def init_db():
    conn = sqlite3.connect("students.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            code TEXT PRIMARY KEY,
            telegram_id INTEGER,
            registered_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()


def main_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text=BTN_PANEL), KeyboardButton(text=BTN_MESSAGE)]],
        resize_keyboard=True
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.effective_chat.id, None)
    await update.message.reply_text(
        "به بات گروه آموزشی حد خوش اومدی 🛡\n"
        "یکی از گزینه‌های پایین صفحه رو انتخاب کن.",
        reply_markup=main_menu()
    )


async def on_panel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
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
    cur.execute("SELECT content FROM codes WHERE code = ?", (code,))
    row = cur.fetchone()

    if not row:
        conn.close()
        await update.message.reply_text("❌ کد واردشده معتبر نیست.")
        return

    content = row[0]
    cur.execute(
        "INSERT OR REPLACE INTO students (code, telegram_id, registered_at) VALUES (?, ?, datetime('now'))",
        (code, chat_id)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ کد تأیید شد، خوش اومدی!\n\n{content}")


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
    """همه پیام‌های متنی که دکمه منو نیستن، از اینجا رد میشن."""
    chat_id = update.effective_chat.id

    # پاسخ ادمین به یه پیام فوروارد شده (ریپلای)
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


async def add_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("فرمت درست:\n/addcode کد محتوا-یا-لینک")
        return
    code = context.args[0]
    content = " ".join(context.args[1:])
    conn = sqlite3.connect("students.db")
    conn.execute("INSERT OR REPLACE INTO codes (code, content) VALUES (?, ?)", (code, content))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"کد «{code}» ثبت شد ✅")


async def list_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    conn = sqlite3.connect("students.db")
    rows = conn.execute("SELECT code, content FROM codes").fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("هیچ کدی ثبت نشده.")
        return
    text = "\n".join([f"• {c} → {t[:40]}" for c, t in rows])
    await update.message.reply_text(text)


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcode", add_code))
    app.add_handler(CommandHandler("codes", list_codes))
    app.add_handler(CallbackQueryHandler(handle_seen, pattern="^seen:"))

    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_PANEL}$"), on_panel_button))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_MESSAGE}$"), on_message_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("بات روشن شد...")
    app.run_polling()


if __name__ == "__main__":
    main()
