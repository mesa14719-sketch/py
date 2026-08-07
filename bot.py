#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import json
import logging
import asyncio
import shutil
import signal
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ============================================================
# 🔧  إعدادات البوت
# ============================================================
BOT_TOKEN = "8708323259:AAHgWVL330obHlpTFJFwYfOi6eBWr4uACHQ"
BASE_DIR = "my_hosting"
DATA_FILE = "bots_data.json"

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

# ============================================================
# 📝  إعداد التسجيل (لتتبع الأخطاء بسهولة)
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================
# 💾  إدارة البيانات
# ============================================================
def save_bots_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"فشل حفظ البيانات: {e}")

def load_bots_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

# تحميل البيانات
bots_data = load_bots_data()
active_bots = {}  # اسم البوت -> كائن العملية

# تهيئة حالة البوتات
for bot_name in list(bots_data.keys()):
    bots_data[bot_name]['running'] = False
save_bots_data(bots_data)

# ============================================================
# 🔄  دوال إدارة العمليات (آمنة ومقاومة للتعليق)
# ============================================================
def stop_process_safely(proc):
    """إيقاف عملية بأمان دون تعليق"""
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    except Exception as e:
        logger.warning(f"خطأ أثناء إيقاف العملية: {e}")

def run_bot_process(file_path):
    """تشغيل بوت فرعي مع التقاط الأخطاء ومنع التعليق"""
    try:
        proc = subprocess.Popen(
            ["python", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return proc
    except Exception as e:
        logger.error(f"فشل تشغيل البوت {file_path}: {e}")
        return None

# ============================================================
# 🤖  دوال البوت الرئيسي
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت جديد", callback_data='upload')],
        [InlineKeyboardButton("📋 عرض البوتات", callback_data='list_bots')]
    ]
    await update.message.reply_text(
        "👋 مرحباً بك في لوحة التحكم الاحترافية!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📤 أرسل لي ملف البوت (.py) الآن."
    )
    return 1

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ جاري استلام الملف...")
    file = update.message.document

    if not file.file_name.endswith(".py"):
        await status_msg.edit_text("❌ يجب أن يكون الملف بصيغة .py")
        return ConversationHandler.END

    bot_name = file.file_name.replace(".py", "")
    bot_folder = os.path.join(BASE_DIR, bot_name)
    os.makedirs(bot_folder, exist_ok=True)
    file_path = os.path.join(bot_folder, file.file_name)

    # تحميل الملف مع مهلة طويلة
    try:
        new_file = await context.bot.get_file(file.file_id)
        await asyncio.wait_for(
            new_file.download_to_drive(file_path),
            timeout=60.0
        )
        await status_msg.edit_text(f"✅ تم تحميل {file.file_name}")
    except asyncio.TimeoutError:
        await status_msg.edit_text("⏰ انتهت مهلة التحميل، حاول مرة أخرى.")
        return ConversationHandler.END
    except Exception as e:
        await status_msg.edit_text(f"❌ فشل التحميل: {e}")
        return ConversationHandler.END

    # تشغيل البوت
    await status_msg.edit_text("⏳ جاري تشغيل البوت...")
    proc = run_bot_process(file_path)
    if proc:
        active_bots[file.file_name] = proc
        bots_data[file.file_name] = {
            'path': file_path,
            'running': True,
            'folder': bot_folder,
            'started_at': datetime.now().isoformat()
        }
        save_bots_data(bots_data)
        await status_msg.edit_text(f"✅ تم تشغيل البوت: {file.file_name}!")
    else:
        await status_msg.edit_text(f"❌ فشل تشغيل {file.file_name}")

    return ConversationHandler.END

async def list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not bots_data:
        await update.callback_query.edit_message_text("📭 لا توجد بوتات مرفوعة.")
        return

    keyboard = []
    for bot_name, info in bots_data.items():
        # تحقق من حالة العملية فعلياً
        proc = active_bots.get(bot_name)
        is_running = proc and proc.poll() is None
        if is_running != info.get('running'):
            info['running'] = is_running
            save_bots_data(bots_data)

        status_text = "🟢 يعمل" if is_running else "🔴 متوقف"
        keyboard.append([
            InlineKeyboardButton(f"{bot_name} - {status_text}", callback_data=f'view_{bot_name}')
        ])

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='back_main')])
    await update.callback_query.edit_message_text(
        "📋 قائمة البوتات:",
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

    proc = active_bots.get(bot_name)
    is_running = proc and proc.poll() is None
    status_text = "🟢 يعمل" if is_running else "🔴 متوقف"

    keyboard = [
        [InlineKeyboardButton("▶️ تشغيل", callback_data=f'run_{bot_name}')],
        [InlineKeyboardButton("⏹️ إيقاف", callback_data=f'stop_{bot_name}')],
        [InlineKeyboardButton("🗑️ حذف", callback_data=f'delete_{bot_name}')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='list_bots')]
    ]
    await query.edit_message_text(
        f"🤖 <b>{bot_name}</b>\n"
        f"📁 المسار: {info['path']}\n"
        f"📌 الحالة: {status_text}\n"
        f"⏰ بدء التشغيل: {info.get('started_at', 'غير معروف')}",
        parse_mode='HTML',
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

    proc = active_bots.get(bot_name)
    if proc and proc.poll() is None:
        await query.edit_message_text("⚠️ البوت يعمل بالفعل.")
        return

    # تشغيل البوت
    new_proc = run_bot_process(info['path'])
    if new_proc:
        active_bots[bot_name] = new_proc
        info['running'] = True
        info['started_at'] = datetime.now().isoformat()
        save_bots_data(bots_data)
        await query.edit_message_text(f"✅ تم تشغيل {bot_name}")
    else:
        await query.edit_message_text(f"❌ فشل تشغيل {bot_name}")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace('stop_', '')
    info = bots_data.get(bot_name)

    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return

    proc = active_bots.get(bot_name)
    if not proc or proc.poll() is not None:
        info['running'] = False
        save_bots_data(bots_data)
        await query.edit_message_text("⚠️ البوت متوقف بالفعل.")
        return

    # إيقاف آمن
    stop_process_safely(proc)
    active_bots.pop(bot_name, None)
    info['running'] = False
    save_bots_data(bots_data)
    await query.edit_message_text(f"⏹️ تم إيقاف {bot_name}")

async def delete_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace('delete_', '')
    info = bots_data.get(bot_name)

    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return

    # إيقاف إذا كان يعمل
    proc = active_bots.get(bot_name)
    if proc and proc.poll() is None:
        stop_process_safely(proc)
        active_bots.pop(bot_name, None)

    # حذف المجلد
    try:
        shutil.rmtree(info['folder'])
    except Exception as e:
        logger.warning(f"لم نتمكن من حذف مجلد {bot_name}: {e}")

    del bots_data[bot_name]
    save_bots_data(bots_data)
    await query.edit_message_text(f"🗑️ تم حذف {bot_name} نهائياً.")

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت جديد", callback_data='upload')],
        [InlineKeyboardButton("📋 عرض البوتات", callback_data='list_bots')]
    ]
    await update.callback_query.edit_message_text(
        "🏠 العودة إلى القائمة الرئيسية:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================
# 🚀  تشغيل البوت مع إعدادات مقاومة للتعليق
# ============================================================
if __name__ == "__main__":
    try:
        logger.info("✅ بدء تشغيل البوت الرئيسي...")

        # إنشاء التطبيق مع مهلات طويلة
        app = (
            ApplicationBuilder()
            .token(BOT_TOKEN)
            .connect_timeout(30.0)
            .read_timeout(120.0)
            .write_timeout(120.0)
            .pool_timeout(120.0)
            .build()
        )

        # إعداد المحادثة
        conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(upload_start, pattern='upload')],
            states={1: [MessageHandler(filters.Document.ALL, handle_file)]},
            fallbacks=[CommandHandler("start", start)],
            per_message=False  # لإصلاح التحذير
        )

        # إضافة المعالجات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv)
        app.add_handler(CallbackQueryHandler(list_bots, pattern='list_bots'))
        app.add_handler(CallbackQueryHandler(view_bot, pattern='^view_'))
        app.add_handler(CallbackQueryHandler(run_bot, pattern='^run_'))
        app.add_handler(CallbackQueryHandler(stop_bot, pattern='^stop_'))
        app.add_handler(CallbackQueryHandler(delete_bot, pattern='^delete_'))
        app.add_handler(CallbackQueryHandler(back_main, pattern='back_main'))

        # معالج أخطاء عام
        async def error_handler(update, context):
            logger.error(f"خطأ: {context.error}")

        app.add_error_handler(error_handler)

        logger.info("✅ البوت جاهز، بدء الاستماع...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    except KeyboardInterrupt:
        logger.info("⏹️ تم إيقاف البوت بواسطتك.")
    except Exception as e:
        logger.error(f"❌ خطأ فادح: {e}")
        sys.exit(1)