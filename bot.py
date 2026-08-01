


import os
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# إعداد المجلدات
BASE_DIR = "my_hosting"
if not os.path.exists(BASE_DIR): os.makedirs(BASE_DIR)

# قاموس لتتبع البوتات المشغلة {bot_name: process_object}
active_bots = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت جديد", callback_data='upload')],
        [InlineKeyboardButton("⚙️ البوتات المشغلة", callback_data='list')]
    ]
    await update.message.reply_text("مرحباً بك في لوحة الاستضافة الاحترافية:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("الآن أرسل ملف البوت (.py) الخاص بك هنا.")
    return 1 # حالة انتظار الملف

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ جاري استلام الملف...")
    file = update.message.document
    
    # التأكد أن الملف بايثون
    if not file.file_name.endswith(".py"):
        await status_msg.edit_text("❌ عذراً، يجب أن يكون الملف بصيغة .py")
        return ConversationHandler.END

    bot_folder = os.path.join(BASE_DIR, file.file_name.replace(".py", ""))
    if not os.path.exists(bot_folder): os.makedirs(bot_folder)
    
    file_path = os.path.join(bot_folder, file.file_name)
    new_file = await context.bot.get_file(file.file_id)
    await new_file.download_to_drive(file_path)
    
    await status_msg.edit_text(f"✅ تم تحميل {file.file_name}، جاري التشغيل...")
    
    # تثبيت المكتبات تلقائياً إذا وجد requirements.txt
    req_path = os.path.join(bot_folder, "requirements.txt")
    if os.path.exists(req_path):
        subprocess.run(["pip", "install", "-r", req_path], capture_output=True)

    try:
        # تشغيل البوت
        proc = subprocess.Popen(["python", file_path])
        active_bots[file.file_name] = proc
        await status_msg.edit_text(f"✅ تم تشغيل البوت: {file.file_name} بنجاح!")
    except Exception as e:
        await status_msg.edit_text(f"❌ حدث خطأ أثناء التشغيل:\n{e}")
        
    return ConversationHandler.END

async def list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not active_bots:
        await update.callback_query.edit_message_text("لا توجد بوتات مشغلة حالياً.")
    else:
        text = "البوتات المشغلة:\n" + "\n".join(active_bots.keys())
        await update.callback_query.edit_message_text(text)

# طلب التوكين عند تشغيل السكريبت
print("="*40)
BOT_TOKEN = "8708323259:AAHgWVL330obHlpTFJFwYfOi6eBWr4uACHQ"
print("جاري تشغيل الاستضافة...")
print("="*40)

app = ApplicationBuilder().token(BOT_TOKEN).build()

# إعداد نظام المحادثة مع إخفاء التحذيرات
conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(upload_start, pattern='upload')],
    states={1: [MessageHandler(filters.Document.ALL, handle_file)]},
    fallbacks=[CommandHandler("start", start)],
    per_message=False
)

app.add_handler(CommandHandler("start", start))
app.add_handler(conv)
app.add_handler(CallbackQueryHandler(list_bots, pattern='list'))

print("نظام الاستضافة الشامل يعمل بنجاح الآن! اذهب للتليجرام واضغط /start")
app.run_polling()
