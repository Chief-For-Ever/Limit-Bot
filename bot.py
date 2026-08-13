import logging
import sqlite3
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ============ تنظیمات (اینا رو پر کن) ============
BOT_TOKEN = "8753659672:AAH0tHsxH3YAG6Ogf8aJUTzGfIzS5e6gSow"          # از BotFather گرفتی
ADMIN_CHAT_ID = 1252988484             # آیدی عددی تلگرام خودت (از @userinfobot بگیر)
PANEL_URL = "https://chief-for-ever.github.io/Limit-panel/"   # لینک limit-panel که تو گیت‌هاب پیجز گرفتی
# ==================================================

logging.basicConfig(level=logging.INFO)

# دانش‌آموزهایی که الان منتظرن پیامشون رو بفرستن
awaiting_message = set()

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
    conn.commit()
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(text="📋 باز کردن پنل", web_app=WebAppInfo(url=PANEL_URL))]],
        resize_keyboard=True
    )
    await update.message.reply_text(
        "به بات گروه آموزشی حد خوش اومدی 🛡\n"
        "با دکمه پایین صفحه، پنل رو باز کن.",
        reply_markup=keyboard
    )


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی کاربر تو Mini App روی «ارسال پیام» می‌زنه، این هندلر صدا زده میشه."""
    chat_id = update.effective_chat.id
    awaiting_message.add(chat_id)
    await update.message.reply_text(
        "✍️ پیامت رو بفرست، مستقیم برای ستاد ارسال میشه."
    )


async def handle_student_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیام متنی دانش‌آموزها. اگه منتظر ارسال بود، فوروارد میشه به ادمین."""
    chat_id = update.effective_chat.id

    if chat_id == ADMIN_CHAT_ID:
        return  # پیام‌های خود ادمین از این تابع رد نمیشه

    if chat_id not in awaiting_message:
        await update.message.reply_text(
            "برای ارسال پیام، اول از منو روی «ارسال پیام» بزن."
        )
        return

    awaiting_message.discard(chat_id)

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


async def handle_seen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی ادمین روی دکمه «دیدم» می‌زنه."""
    query = update.callback_query
    await query.answer()

    student_chat_id = int(query.data.split(":")[1])
    await context.bot.send_message(
        chat_id=student_chat_id,
        text="پیامت دیده شد 👁"
    )
    await query.edit_message_reply_markup(reply_markup=None)


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی ادمین روی یکی از پیام‌های فوروارد شده ریپلای می‌زنه، برای همون دانش‌آموز میره."""
    replied = update.message.reply_to_message
    if not replied or replied.message_id not in forward_map:
        return

    student_chat_id = forward_map[replied.message_id]
    await context.bot.send_message(
        chat_id=student_chat_id,
        text=update.message.text
    )


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(CallbackQueryHandler(handle_seen, pattern="^seen:"))

    # ریپلای ادمین به پیام‌های فوروارد شده
    app.add_handler(MessageHandler(
        filters.REPLY & filters.User(ADMIN_CHAT_ID) & filters.TEXT,
        handle_admin_reply
    ))

    # پیام معمولی دانش‌آموزها
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_student_text
    ))

    print("بات روشن شد...")
    app.run_polling()


if __name__ == "__main__":
    main()
