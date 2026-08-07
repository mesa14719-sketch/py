#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import shutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ============================================================
TOKEN = "8708323259:AAHgWVL330obHlpTFJFwYfOi6eBWr4uACHQ"
BASE = "my_hosting"
DATA = "bots_data.json"
os.makedirs(BASE, exist_ok=True)

def save(d):
    with open(DATA, "w") as f: json.dump(d, f, indent=4)

def load():
    if os.path.exists(DATA):
        with open(DATA, "r") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    return {}

bots = load()
procs = {}

async def start(update, context):
    kb = [[InlineKeyboardButton("📂 رفع بوت", callback_data="upload")],
          [InlineKeyboardButton("📋 القائمة", callback_data="list")]]
    await update.message.reply_text("👋 مرحباً!", reply_markup=InlineKeyboardMarkup(kb))

async def upload_start(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📤 أرسل ملف .py")
    return 1

async def handle_file(update, context):
    msg = await update.message.reply_text("⏳ جاري الاستلام...")
    file = update.message.document
    if not file.file_name.endswith(".py"):
        await msg.edit_text("❌ يجب أن يكون .py")
        return ConversationHandler.END
    name = file.file_name.replace(".py", "")
    folder = os.path.join(BASE, name)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, file.file_name)
    try:
        f = await context.bot.get_file(file.file_id)
        await f.download_to_drive(path)
        p = subprocess.Popen(["python", path])
        procs[name] = p
        bots[name] = {"path": path, "running": True, "folder": folder}
        save(bots)
        await msg.edit_text(f"✅ تم تشغيل {name}")
    except Exception as e:
        await msg.edit_text(f"❌ فشل: {e}")
    return ConversationHandler.END

async def list_bots(update, context):
    await update.callback_query.answer()
    if not bots:
        await update.callback_query.edit_message_text("📭 لا توجد بوتات")
        return
    kb = []
    for n, i in bots.items():
        p = procs.get(n)
        st = "🟢 يعمل" if (p and p.poll() is None) else "🔴 متوقف"
        kb.append([InlineKeyboardButton(f"{n} - {st}", callback_data=f"v_{n}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
    await update.callback_query.edit_message_text("📋 القائمة:", reply_markup=InlineKeyboardMarkup(kb))

async def view_bot(update, context):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("v_", "")
    info = bots.get(name)
    if not info:
        await q.edit_message_text("❌ غير موجود")
        return
    p = procs.get(name)
    st = "🟢 يعمل" if (p and p.poll() is None) else "🔴 متوقف"
    kb = [[InlineKeyboardButton("▶️ تشغيل", callback_data=f"run_{name}")],
          [InlineKeyboardButton("⏹️ إيقاف", callback_data=f"stop_{name}")],
          [InlineKeyboardButton("🗑️ حذف", callback_data=f"del_{name}")],
          [InlineKeyboardButton("🔙 رجوع", callback_data="list")]]
    await q.edit_message_text(f"🤖 {name}\n📌 {st}", reply_markup=InlineKeyboardMarkup(kb))

async def run_bot(update, context):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("run_", "")
    info = bots.get(name)
    if not info:
        await q.edit_message_text("❌ غير موجود")
        return
    p = procs.get(name)
    if p and p.poll() is None:
        await q.edit_message_text("⚠️ يعمل")
        return
    try:
        p = subprocess.Popen(["python", info["path"]])
        procs[name] = p
        info["running"] = True
        save(bots)
        await q.edit_message_text(f"✅ تم تشغيل {name}")
    except Exception as e:
        await q.edit_message_text(f"❌ فشل: {e}")

async def stop_bot(update, context):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("stop_", "")
    info = bots.get(name)
    if not info:
        await q.edit_message_text("❌ غير موجود")
        return
    p = procs.get(name)
    if not p or p.poll() is not None:
        await q.edit_message_text("⚠️ متوقف")
        return
    try:
        p.terminate()
        try:
            p.wait(timeout=3)
        except:
            p.kill()
        procs.pop(name, None)
        info["running"] = False
        save(bots)
        await q.edit_message_text(f"⏹️ تم إيقاف {name}")
    except:
        await q.edit_message_text("❌ فشل")

async def delete_bot(update, context):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("del_", "")
    info = bots.get(name)
    if not info:
        await q.edit_message_text("❌ غير موجود")
        return
    p = procs.get(name)
    if p and p.poll() is None:
        try:
            p.terminate()
            try:
                p.wait(timeout=3)
            except:
                p.kill()
        except:
            pass
        procs.pop(name, None)
    try:
        shutil.rmtree(info["folder"])
    except:
        pass
    del bots[name]
    save(bots)
    await q.edit_message_text(f"🗑️ تم حذف {name}")

async def back(update, context):
    await update.callback_query.answer()
    kb = [[InlineKeyboardButton("📂 رفع بوت", callback_data="upload")],
          [InlineKeyboardButton("📋 القائمة", callback_data="list")]]
    await update.callback_query.edit_message_text("🏠 القائمة:", reply_markup=InlineKeyboardMarkup(kb))

# ============================================================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_start, pattern="upload")],
        states={1: [MessageHandler(filters.Document.ALL, handle_file)]},
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(list_bots, pattern="list"))
    app.add_handler(CallbackQueryHandler(view_bot, pattern="^v_"))
    app.add_handler(CallbackQueryHandler(run_bot, pattern="^run_"))
    app.add_handler(CallbackQueryHandler(stop_bot, pattern="^stop_"))
    app.add_handler(CallbackQueryHandler(delete_bot, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(back, pattern="back"))
    print("✅ البوت يعمل!")
    app.run_polling()
