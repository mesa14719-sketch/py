#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import json
import logging
import shutil
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
# 🔧  الإعدادات الأساسية
# ============================================================
BOT_TOKEN = "8708323259:AAHgWVL330obHlpTFJFwYfOi6eBWr4uACHQ"
BASE_DIR = "my_hosting"
DATA_FILE = "bots_data.json"

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# 💾  حفظ وتحميل البيانات
# ============================================================
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    return {}

bots = load_data()
processes = {}

# ============================================================
# 🤖  دوال البوت
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت", callback_data="upload")],
        [InlineKeyboardButton("📋 قائمة البوتات", callback_data="list")],
    ]
    await update.message.reply_text("👋 مرحباً! اختر خياراً:", reply_markup=InlineKeyboardMarkup(keyboard))

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📤 أرسل ملف (.py) الآن.")
    return 1

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ جاري الاستلام...")
    file = update.message.document

    if not file.file_name.endswith(".py"):
        await msg.edit_text("❌ يجب أن يكون الملف .py")
        return ConversationHandler.END

    name = file.file_name.replace(".py", "")
    folder = os.path.join(BASE_DIR, name)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, file.file_name)

    try:
        f = await context.bot.get_file(file.file_id)
        await f.download_to_drive(path)
        proc = subprocess.Popen(["python", path])
        processes[name] = proc
        bots[name] = {"path": path, "running": True, "folder": folder}
        save_data(bots)
        await msg.edit_text(f"✅ تم تشغيل {name}")
    except Exception as e:
        await msg.edit_text(f"❌ فشل: {e}")
    return ConversationHandler.END

async def list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not bots:
        await update.callback_query.edit_message_text("📭 لا توجد بوتات.")
        return
    keyboard = []
    for name, info in bots.items():
        p = processes.get(name)
        status = "🟢 يعمل" if (p and p.poll() is None) else "🔴 متوقف"
        keyboard.append([InlineKeyboardButton(f"{name} - {status}", callback_data=f"v_{name}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
    await update.callback_query.edit_message_text("📋 قائمة البوتات:", reply_markup=InlineKeyboardMarkup(keyboard))

async def view_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("v_", "")
    info = bots.get(name)
    if not info:
        await q.edit_message_text("❌ غير موجود.")
        return
    p = processes.get(name)
    status = "🟢 يعمل" if (p and p.poll() is None) else "🔴 متوقف"
    keyboard = [
        [InlineKeyboardButton("▶️ تشغيل", callback_data=f"run_{name}")],
        [InlineKeyboardButton("⏹️ إيقاف", callback_data=f"stop_{name}")],
        [InlineKeyboardButton("🗑️ حذف", callback_data=f"del_{name}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="list")],
    ]
    await q.edit_message_text(f"🤖 {name}\n📌 الحالة: {status}", reply_markup=InlineKeyboardMarkup(keyboard))

async def run_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("run_", "")
    info = bots.get(name)
    if not info:
        await q.edit_message_text("❌ غير موجود")
        return
    p = processes.get(name)
    if p and p.poll() is None:
        await q.edit_message_text("⚠️ يعمل بالفعل")
        return
    try:
        proc = subprocess.Popen(["python", info["path"]])
        processes[name] = proc
        info["running"] = True
        save_data(bots)
        await q.edit_message_text(f"✅ تم تشغيل {name}")
    except Exception as e:
        await q.edit_message_text(f"❌ فشل: {e}")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("stop_", "")
    info = bots.get(name)
    if not info:
        await q.edit_message_text("❌ غير موجود")
        return
    p = processes.get(name)
    if not p or p.poll() is not None:
        await q.edit_message_text("⚠️ متوقف بالفعل")
        return
    try:
        p.terminate()
        try:
            p.wait(timeout=3)
        except:
            p.kill()
        processes.pop(name, None)
        info["running"] = False
        save_data(bots)
        await q.edit_message_text(f"⏹️ تم إيقاف {name}")
    except:
        await q.edit_message_text("❌ فشل الإيقاف")

async def delete_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("del_", "")
    info = bots.get(name)
    if not info:
        await q.edit_message_text("❌ غير موجود")
        return
    p = processes.get(name)
    if p and p.poll() is None:
        try:
            p.terminate()
            try:
                p.wait(timeout=3)
            except:
                p.kill()
        except:
            pass
        processes.pop(name, None)
    try:
        shutil.rmtree(info["folder"])
    except:
        pass
    del bots[name]
    save_data(bots)
    await q.edit_message_text(f"🗑️ تم حذف {name}")

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [
        [InlineKeyboardButton("📂 رفع بوت", callback_data="upload")],
        [InlineKeyboardButton("📋 قائمة البوتات", callback_data="list")],
    ]
    await update.callback_query.edit_message_text("🏠 القائمة الرئيسية:", reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================================
# 🚀  التشغيل
# ============================================================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_start, pattern="upload")],
        states={1: [MessageHandler(filters.Document.ALL, handle_file)]},
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(list_bots, pattern="list"))
    app.add_handler(CallbackQueryHandler(view_bot, pattern="^v_"))
    app.add_handler(CallbackQueryHandler(run_bot, pattern="^run_"))
    app.add_handler(CallbackQueryHandler(stop_bot, pattern="^stop_"))
    app.add_handler(CallbackQueryHandler(delete_bot, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(back, pattern="back"))

    logger.info("✅ البوت يعمل!")
    app.run_polling()
