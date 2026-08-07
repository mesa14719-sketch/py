#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import json
import logging
import shutil
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ============================================================
# 🔧  التوكن مباشرة (عدّل هنا إذا أردت تغييره)
# ============================================================
BOT_TOKEN = "8708323259:AAHgWVL330obHlpTFJFwYfOi6eBWr4uACHQ"

BASE_DIR = "my_hosting"
DATA_FILE = "bots_data.json"

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# 💾  إدارة البيانات
# ============================================================
def save_bots_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"فشل حفظ البيانات: {e}")

def load_bots_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

bots_data = load_bots_data()
active_bots = {}

for bot_name in list(bots_data.keys()):
    bots_data[bot_name]["running"] = False
save_bots_data(bots_data)

# ============================================================
# 🤖  دوال البوت
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت جديد", callback_data="upload")],
        [InlineKeyboardButton("📋 عرض البوتات", callback_data="list_bots")],
    ]
    await update.message.reply_text(
        "👋 مرحباً بك في لوحة التحكم!",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📤 أرسل ملف البوت (.py) الآن.")
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

    try:
        new_file = await context.bot.get_file(file.file_id)
        await new_file.download_to_drive(file_path)
        await status_msg.edit_text(f"✅ تم تحميل {file.file_name}")
    except Exception as e:
        await status_msg.edit_text(f"❌ فشل التحميل: {e}")
        return ConversationHandler.END

    try:
        proc = subprocess.Popen(["python", file_path])
        active_bots[file.file_name] = proc
        bots_data[file.file_name] = {
            "path": file_path,
            "running": True,
            "folder": bot_folder,
            "started_at": datetime.now().isoformat(),
        }
        save_bots_data(bots_data)
        await status_msg.edit_text(f"✅ تم تشغيل البوت: {file.file_name}!")
    except Exception as e:
        await status_msg.edit_text(f"❌ فشل التشغيل: {e}")

    return ConversationHandler.END

async def list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not bots_data:
        await update.callback_query.edit_message_text("📭 لا توجد بوتات.")
        return

    keyboard = []
    for bot_name, info in bots_data.items():
        proc = active_bots.get(bot_name)
        is_running = proc and proc.poll() is None
        if is_running != info.get("running"):
            info["running"] = is_running
            save_bots_data(bots_data)

        status_text = "🟢 يعمل" if is_running else "🔴 متوقف"
        keyboard.append([
            InlineKeyboardButton(
                f"{bot_name} - {status_text}",
                callback_data=f"view_{bot_name}",
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    await update.callback_query.edit_message_text(
        "📋 قائمة البوتات:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def view_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace("view_", "")
    info = bots_data.get(bot_name)
    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return

    proc = active_bots.get(bot_name)
    is_running = proc and proc.poll() is None
    status_text = "🟢 يعمل" if is_running else "🔴 متوقف"

    keyboard = [
        [InlineKeyboardButton("▶️ تشغيل", callback_data=f"run_{bot_name}")],
        [InlineKeyboardButton("⏹️ إيقاف", callback_data=f"stop_{bot_name}")],
        [InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_{bot_name}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="list_bots")],
    ]
    await query.edit_message_text(
        f"🤖 <b>{bot_name}</b>\n"
        f"📂 المسار: {info['path']}\n"
        f"📌 الحالة: {status_text}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def run_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace("run_", "")
    info = bots_data.get(bot_name)
    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return

    proc = active_bots.get(bot_name)
    if proc and proc.poll() is None:
        await query.edit_message_text("⚠️ البوت يعمل بالفعل.")
        return

    try:
        new_proc = subprocess.Popen(["python", info["path"]])
        active_bots[bot_name] = new_proc
        info["running"] = True
        info["started_at"] = datetime.now().isoformat()
        save_bots_data(bots_data)
        await query.edit_message_text(f"✅ تم تشغيل {bot_name}")
    except Exception as e:
        await query.edit_message_text(f"❌ فشل التشغيل: {e}")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace("stop_", "")
    info = bots_data.get(bot_name)
    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return

    proc = active_bots.get(bot_name)
    if not proc or proc.poll() is not None:
        info["running"] = False
        save_bots_data(bots_data)
        await query.edit_message_text("⚠️ البوت متوقف بالفعل.")
        return

    try:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    except Exception:
        pass

    active_bots.pop(bot_name, None)
    info["running"] = False
    save_bots_data(bots_data)
    await query.edit_message_text(f"⏹️ تم إيقاف {bot_name}")

async def delete_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_name = query.data.replace("delete_", "")
    info = bots_data.get(bot_name)
    if not info:
        await query.edit_message_text("❌ البوت غير موجود.")
        return

    proc = active_bots.get(bot_name)
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        except:
            pass
        active_bots.pop(bot_name, None)

    try:
        shutil.rmtree(info["folder"])
    except:
        pass

    del bots_data[bot_name]
    save_bots_data(bots_data)
    await query.edit_message_text(f"🗑️ تم حذف {bot_name} نهائياً.")

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت جديد", callback_data="upload")],
        [InlineKeyboardButton("📋 عرض البوتات", callback_data="list_bots")],
    ]
    await update.callback_query.edit_message_text(
        "🏠 القائمة الرئيسية:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ============================================================
# 🚀  التشغيل
# ============================================================
if __name__ == "__main__":
    try:
        logger.info("✅ بدء تشغيل البوت الرئيسي...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()

        conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(upload_start, pattern="upload")],
            states={1: [MessageHandler(filters.Document.ALL, handle_file)]},
            fallbacks=[CommandHandler("start", start)],
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv)
        app.add_handler(CallbackQueryHandler(list_bots, pattern="list_bots"))
        app.add_handler(CallbackQueryHandler(view_bot, pattern="^view_"))
        app.add_handler(CallbackQueryHandler(run_bot, pattern="^run_"))
        app.add_handler(CallbackQueryHandler(stop_bot, pattern="^stop_"))
        app.add_handler(CallbackQueryHandler(delete_bot, pattern="^delete_"))
        app.add_handler(CallbackQueryHandler(back_main, pattern="back_main"))

        logger.info("✅ البوت جاهز، بدء الاستماع...")
        app.run_polling()
    except Exception as e:
        logger.error(f"❌ خطأ فادح: {e}")
        sys.exit(1)
