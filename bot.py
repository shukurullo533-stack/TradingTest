
import os
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

# ==================================
# BOT SOZLAMALARI
# ==================================

TOKEN = os.getenv("9244793379:AAGF7Jb6pamh5n3T9lFkZv50JqiAaXA_60g", "9244793379:AAGXtZrud62NsTad9Hhc-fNg6X4HPqCynbQ").strip()
ADMIN_PASSWORD = os.getenv("535157", "575953").strip()

OWNER_ID = int(os.getenv("OWNER_ID", "8344141174"))

DB_FILE = "bot_data.json"
MIN_INTERVAL = 60


# ==================================
# MA'LUMOTLAR
# ==================================

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                result = json.load(f)
        except Exception:
            result = {}
    else:
        result = {}

    result.setdefault("groups", [])
    result.setdefault("message", "")
    result.setdefault("interval", 300)
    result.setdefault("admin_ids", [OWNER_ID])
    result.setdefault("pending_admins", {})

    if OWNER_ID not in result["admin_ids"]:
        result["admin_ids"].append(OWNER_ID)

    return result


data = load_data()


def save_data():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def is_admin(user_id):
    return user_id in data["admin_ids"]


# ==================================
# ADMIN MENYUSI
# ==================================

def menu():
    keyboard = [
        [
            InlineKeyboardButton("✍️ Xabar yozish", callback_data="message"),
            InlineKeyboardButton("⏱ Vaqt sozlash", callback_data="interval"),
        ],
        [
            InlineKeyboardButton("▶️ Boshlash", callback_data="start"),
            InlineKeyboardButton("⏹ To‘xtatish", callback_data="stop"),
        ],
        [
            InlineKeyboardButton("👥 Guruhlar", callback_data="groups"),
            InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("👑 Adminlar", callback_data="admins"),
        ],
        [
            InlineKeyboardButton("🔒 Chiqish", callback_data="logout"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def show_menu_text():
    return "👑 ADMIN PANELI\n\nKerakli bo‘limni tanlang:"


async def send_menu(message):
    await message.reply_text(
        show_menu_text(),
        reply_markup=menu()
    )


# ==================================
# /START
# ==================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if not is_admin(uid):

        pending = data["pending_admins"]

        if str(uid) in pending:
            await update.message.reply_text(
                "⏳ Adminlik so‘rovingiz yuborilgan. "
                "Asosiy admin tasdiqlashini kuting."
            )
            return

        pending[str(uid)] = {
            "name": user.full_name,
            "username": user.username or ""
        }
        save_data()

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "✅ Tasdiqlash",
                callback_data=f"admin:approve:{uid}"
            ),
            InlineKeyboardButton(
                "❌ Rad etish",
                callback_data=f"admin:reject:{uid}"
            )
        ]])

        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    "🔔 YANGI ADMIN SO‘ROVI\n\n"
                    f"Ismi: {user.full_name}\n"
                    f"Username: @{user.username or 'yo‘q'}\n"
                    f"Telegram ID: {uid}"
                ),
                reply_markup=keyboard
            )

        except Exception as e:
            print("Admin so‘rovi yuborilmadi:", e)

            await update.message.reply_text(
                "❌ Asosiy adminga xabar yuborilmadi. "
                "Asosiy admin botga avval /start yuborganini tekshiring."
            )
            return

        await update.message.reply_text(
            "✅ Adminlik so‘rovingiz asosiy adminga yuborildi."
        )
        return

    if context.user_data.get("authenticated"):
        await send_menu(update.message)
        return

    context.user_data["awaiting_code"] = True

    await update.message.reply_text(
        "🔐 ADMIN KIRISH\n\n"
        "Umumiy admin kodini kiriting:"
    )


# ==================================
# GURUHLARNI ANIQLASH
# ==================================

async def group_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member

    if not result:
        return

    chat = result.chat
    status = result.new_chat_member.status

    if chat.type not in ("group", "supergroup"):
        return

    if status in ("member", "administrator"):
        if chat.id not in data["groups"]:
            data["groups"].append(chat.id)
            save_data()

    elif status in ("left", "kicked"):
        if chat.id in data["groups"]:
            data["groups"].remove(chat.id)
            save_data()


# ==================================
# GURUHLARGA XABAR YUBORISH
# ==================================

async def broadcast(context: ContextTypes.DEFAULT_TYPE):
    message = data.get("message", "")

    if not message:
        return

    for group_id in list(data["groups"]):
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=message
            )

        except Exception as e:
            print(f"Guruhga yuborishda xato {group_id}: {e}")


# ==================================
# TUGMALAR
# ==================================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    action = query.data

    # ADMIN SO‘ROVINI TASDIQLASH
    if action.startswith("admin:approve:"):

        if user_id != OWNER_ID:
            await query.message.reply_text(
                "❌ Siz asosiy admin emassiz."
            )
            return

        new_admin = int(action.split(":")[2])
        pending = data["pending_admins"]

        if str(new_admin) not in pending:
            await query.edit_message_text(
                "Bu so‘rov topilmadi yoki oldin ko‘rib chiqilgan."
            )
            return

        if new_admin not in data["admin_ids"]:
            data["admin_ids"].append(new_admin)

        pending.pop(str(new_admin), None)
        save_data()

        await query.edit_message_text(
            "✅ Adminlik so‘rovi tasdiqlandi."
        )

        try:
            await context.bot.send_message(
                chat_id=new_admin,
                text="✅ Adminlik so‘rovingiz tasdiqlandi. Botga /start yuboring."
            )
        except Exception as e:
            print("Yangi adminga xabar yuborilmadi:", e)

        return

    # ADMIN SO‘ROVINI RAD ETISH
    if action.startswith("admin:reject:"):

        if user_id != OWNER_ID:
            await query.message.reply_text(
                "❌ Siz asosiy admin emassiz."
            )
            return

        rejected_admin = int(action.split(":")[2])

        if str(rejected_admin) not in data["pending_admins"]:
            await query.edit_message_text(
                "Bu so‘rov topilmadi yoki oldin ko‘rib chiqilgan."
            )
            return

        data["pending_admins"].pop(str(rejected_admin), None)
        save_data()

        await query.edit_message_text(
            "❌ Adminlik so‘rovi rad etildi."
        )

        try:
            await context.bot.send_message(
                chat_id=rejected_admin,
                text="Adminlik so‘rovingiz rad etildi."
            )
        except Exception as e:
            print("Foydalanuvchiga xabar yuborilmadi:", e)

        return

    # ADMIN TEKSHIRUVI
    if not is_admin(user_id):
        await query.message.reply_text("❌ Siz admin emassiz.")
        return

    if not context.user_data.get("authenticated"):
        await query.message.reply_text(
            "Avval admin kodini kiriting: /start"
        )
        return

    # XABAR YOZISH
    if action == "message":
        context.user_data["awaiting_message"] = True
        await query.message.reply_text(
            "✍️ Yuboriladigan xabarni yozing:"
        )

    # VAQT SOZLASH
    elif action == "interval":
        context.user_data["awaiting_interval"] = True
        await query.message.reply_text(
            "⏱ Xabarlar orasidagi vaqtni sekundda kiriting.\n"
            "Eng kamida 60 sekund."
        )

    # GURUHLAR
    elif action == "groups":
        await query.message.reply_text(
            f"👥 Bot qo‘shilgan guruhlar soni: {len(data['groups'])}"
        )

    # STATISTIKA
    elif action == "stats":
        jobs = (
            context.job_queue.get_jobs_by_name("broadcast")
            if context.job_queue else []
        )

        status = "Ishlayapti 🟢" if jobs else "To‘xtatilgan 🔴"

        await query.message.reply_text(
            "📊 STATISTIKA\n\n"
            f"Guruhlar: {len(data['groups'])}\n"
            f"Holati: {status}\n"
            f"Oraliq: {data['interval']} sekund"
        )

    # BOSHLASH
    elif action == "start":

        if not data["groups"]:
            await query.message.reply_text(
                "❌ Avval botni guruhga qo‘shing."
            )
            return

        if not data["message"]:
            await query.message.reply_text(
                "❌ Avval yuboriladigan xabarni kiriting."
            )
            return

        if context.job_queue is None:
            await query.message.reply_text(
                "❌ JobQueue ishlamayapti. Kutubxonani tekshiring."
            )
            return

        old_jobs = context.job_queue.get_jobs_by_name("broadcast")

        if old_jobs:
            await query.message.reply_text(
                "Xabar yuborish allaqachon ishlayapti."
            )
            return

        context.job_queue.run_repeating(
            broadcast,
            interval=max(MIN_INTERVAL, int(data["interval"])),
            first=0,
            name="broadcast"
        )

        await query.message.reply_text(
            "✅ Xabar yuborish boshlandi!"
        )

    # TO‘XTATISH
    elif action == "stop":

        if context.job_queue is None:
            await query.message.reply_text(
                "JobQueue ishlamayapti."
            )
            return

        jobs = context.job_queue.get_jobs_by_name("broadcast")

        if not jobs:
            await query.message.reply_text(
                "Xabar yuborish hozir ishlamayapti."
            )
            return

        for job in jobs:
            job.schedule_removal()

        await query.message.reply_text(
            "⛔ Xabar yuborish to‘xtatildi!"
        )

    # ADMINLAR
    elif action == "admins":
        admins = data["admin_ids"]
        text_admins = "\n".join(str(x) for x in admins)

        await query.message.reply_text(
            "👑 ADMINLAR RO‘YXATI:\n\n" + text_admins
        )

    # CHIQISH
    elif action == "logout":
        context.user_data["authenticated"] = False

        await query.message.reply_text(
            "🔒 Admin paneldan chiqdingiz. "
            "Qayta kirish uchun /start yuboring."
        )


# ==================================
# FOYDALANUVCHI XABARLARI
# ==================================

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ADMIN PAROLI
    if context.user_data.get("awaiting_code"):
        context.user_data["awaiting_code"] = False

        if text == ADMIN_PASSWORD:

            if not is_admin(user_id):
                await update.message.reply_text(
                    "Siz admin sifatida tasdiqlanmagansiz."
                )
                return

            context.user_data["authenticated"] = True

            await update.message.reply_text(
                "✅ Admin panelga xush kelibsiz!"
            )

            await send_menu(update.message)
        else:
            await update.message.reply_text(
                "❌ Admin kodi noto‘g‘ri. Qayta /start yuboring."
            )

        return

    # XABAR SAQLASH
    if context.user_data.get("awaiting_message"):
        context.user_data["awaiting_message"] = False

        if not is_admin(user_id) or not context.user_data.get("authenticated"):
            await update.message.reply_text(
                "Avval admin panelga kiring."
            )
            return

        data["message"] = text
        save_data()

        await update.message.reply_text(
            "✅ Xabar saqlandi. Endi Boshlash tugmasini bosing."
        )

        await send_menu(update.message)
        return

    # VAQT SAQLASH
    if context.user_data.get("awaiting_interval"):
        context.user_data["awaiting_interval"] = False

        if not is_admin(user_id) or not context.user_data.get("authenticated"):
            await update.message.reply_text(
                "Avval admin panelga kiring."
            )
            return

        try:
            interval = int(text)

            if interval < MIN_INTERVAL:
                await update.message.reply_text(
                    "❌ Eng kamida 60 sekund kiriting."
                )
                context.user_data["awaiting_interval"] = True
                return

            data["interval"] = interval
            save_data()

            await update.message.reply_text(
                f"✅ Vaqt saqlandi: {interval} sekund."
            )

            await send_menu(update.message)

        except ValueError:
            await update.message.reply_text(
                "❌ Faqat son kiriting. Masalan: 300"
            )
            context.user_data["awaiting_interval"] = True

        return


# ==================================
# XATOLIKLARNI ANIQLASH
# ==================================

async def error_handler(update, context):
    print("Botda xatolik:", context.error)


# ==================================
# BOTNI ISHGA TUSHIRISH
# ==================================

def main():

    if not TOKEN:
        raise ValueError(
            "BOT_TOKEN kiritilmagan! CMD orqali tokenni sozlang."
        )

    if not ADMIN_PASSWORD:
        raise ValueError(
            "ADMIN_PASSWORD kiritilmagan! CMD orqali parolni sozlang."
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(buttons)
    )

    app.add_handler(
        ChatMemberHandler(
            group_member,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_text
        )
    )

    app.add_error_handler(error_handler)

    print("SHUKURULLO CONTROL BOT ISHGA TUSHDI!")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
