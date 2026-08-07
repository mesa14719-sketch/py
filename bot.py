import os
import subprocess
import json
import signal
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# إعداد المجلدات
BASE_DIR = "my_hosting"
DATA_FILE = "bots_data.json"

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

# تحميل البيانات المخزنة
def load_bots_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_bots_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# تحميل البيانات
bots_data = load_bots_data()
active_bots = {}  # {bot_name: process_object}

# استعادة العمليات النشطة (إن كانت موجودة) - سنحتفظ بها عند بدء التشغيل
# لكننا لا نستطيع استعادة العمليات السابقة، لذا سنعتبر الجميع موقوفة عند بدء التشغيل
# وسنحدث البيانات لتكون الحالة false عند بدء التشغيل
for bot_name in bots_data:
    bots_data[bot_name]['running'] = False
save_bots_data(bots_data)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت جديد", callback_data='upload')],
        [InlineKeyboardButton("📋 عرض البوتات المرفوعة", callback_data='list_bots')]
    ]
    await update.message.reply_text("مرحباً بك في لوحة التحكم الاحترافية:\nاختر أحد الخيارات:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("الآن أرسل ملف البوت (.py) الخاص بك هنا.")
    return 1  # حالة انتظار الملف

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ جاري استلام الملف...")
    file = update.message.document
    
    if not file.file_name.endswith(".py"):
        await status_msg.edit_text("❌ عذراً، يجب أن يكون الملف بصيغة .py")
        return ConversationHandler.END

    bot_name = file.file_name.replace(".py", "")
    bot_folder = os.path.join(BASE_DIR, bot_name)
    if not os.path.exists(bot_folder):
        os.makedirs(bot_folder)
    
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
        # حفظ البيانات
        bots_data[file.file_name] = {
            'path': file_path,
            'running': True,
            'folder': bot_folder
        }
        save_bots_data(bots_data)
        await status_msg.edit_text(f"✅ تم تشغيل البوت: {file.file_name} بنجاح!")
    except Exception as e:
        await status_msg.edit_text(f"❌ حدث خطأ أثناء التشغيل:\n{e}")
        
    return ConversationHandler.END

async def list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not bots_data:
        await update.callback_query.edit_message_text("لا توجد بوتات مرفوعة حالياً.")
        return
    
    keyboard = []
    for bot_name, info in bots_data.items():
        status_text = "🟢 يعمل" if info['running'] else "🔴 متوقف"
        button_text = f"{bot_name} - {status_text}"
        # نضيف أزرار التحكم لكل بوت
        row = [
            InlineKeyboardButton(button_text, callback_data=f'view_{bot_name}')
        ]
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data='back_main')])
    await update.callback_query.edit_message_text(
        "📋 قائمة البوتات المرفوعة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def view_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace('view_', '')
    info = bots_data.get(bot_name)
    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return
    
    status_text = "🟢 يعمل" if info['running'] else "🔴 متوقف"
    keyboard = [
        [InlineKeyboardButton("▶️ تشغيل", callback_data=f'run_{bot_name}')],
        [InlineKeyboardButton("⏹️ إيقاف", callback_data=f'stop_{bot_name}')],
        [InlineKeyboardButton("🗑️ حذف", callback_data=f'delete_{bot_name}')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='list_bots')]
    ]
    await query.edit_message_text(
        f"🤖 البوت: {bot_name}\n"
        f"📂 المسار: {info['path']}\n"
        f"📌 الحالة: {status_text}\n\n"
        "اختر الإجراء المناسب:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def run_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace('run_', '')
    info = bots_data.get(bot_name)
    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return
    if info['running']:
        await query.edit_message_text("⚠️ البوت يعمل بالفعل.")
        return
    
    try:
        proc = subprocess.Popen(["python", info['path']])
        active_bots[bot_name] = proc
        info['running'] = True
        save_bots_data(bots_data)
        await query.edit_message_text(f"✅ تم تشغيل البوت {bot_name} بنجاح.")
    except Exception as e:
        await query.edit_message_text(f"❌ فشل التشغيل: {e}")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace('stop_', '')
    info = bots_data.get(bot_name)
    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return
    if not info['running']:
        await query.edit_message_text("⚠️ البوت متوقف بالفعل.")
        return
    
    proc = active_bots.get(bot_name)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    info['running'] = False
    active_bots.pop(bot_name, None)
    save_bots_data(bots_data)
    await query.edit_message_text(f"⏹️ تم إيقاف البوت {bot_name}.")

async def delete_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace('delete_', '')
    info = bots_data.get(bot_name)
    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return
    
    # إيقاف البوت إذا كان يعمل
    if info['running']:
        proc = active_bots.get(bot_name)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        active_bots.pop(bot_name, None)
    
    # حذف المجلد
    import shutil
    try:
        shutil.rmtree(info['folder'])
    except Exception as e:
        await query.edit_message_text(f"⚠️ لم نتمكن من حذف الملفات: {e}")
    
    # حذف البيانات
    del bots_data[bot_name]
    save_bots_data(bots_data)
    await query.edit_message_text(f"🗑️ تم حذف البوت {bot_name} نهائياً.")

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت جديد", callback_data='upload')],
        [InlineKeyboardButton("📋 عرض البوتات المرفوعة", callback_data='list_bots')]
    ]
    await update.callback_query.edit_message_text(
        "مرحباً بك في لوحة التحكم الاحترافية:\nاختر أحد الخيارات:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# طلب التوكين عند تشغيل السكريبت
print("=" * 40)
BOT_TOKEN = "8708323259:AAHgWVL330obHlpTFJFwYfOi6eBWr4uACHQ"
print("جاري تشغيل الاستضافة...")
print("=" * 40)

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
app.add_handler(CallbackQueryHandler(list_bots, pattern='list_bots'))
app.add_handler(CallbackQueryHandler(view_bot, pattern='^view_'))
app.add_handler(CallbackQueryHandler(run_bot, pattern='^run_'))
app.add_handler(CallbackQueryHandler(stop_bot, pattern='^stop_'))
app.add_handler(CallbackQueryHandler(delete_bot, pattern='^delete_'))
app.add_handler(CallbackQueryHandler(back_main, pattern='back_main'))

print("نظام الاستضافة الشامل يعمل بنجاح الآن! اذهب للتليجرام واضغط /start")
app.run_polling()
