import json
import os
import hashlib
import secrets

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters
)

# BOT SOZLAMALARI
TOKEN = "9244793379:AAGF7Jb6pamh5n3T9lFkZv50JqiAaXA_60g"
OWNER_ID = 8344141174
ADMIN_PASSWORD = "535157"

DB_FILE = "bot_data.json"
MIN_INTERVAL = 60


# MA'LUMOTLARNI YUKLASH
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                result = json.load(f)
        except (json.JSONDecodeError, OSError):
            result = {}
    else:
        result = {}

    result.setdefault("groups", [])
    result.setdefault("message", "")
    result.setdefault("interval", 300)
    result.setdefault("admin_ids", [OWNER_ID])
    result.setdefault("pending_admins", {})
    result.setdefault("admin_passwords", {})

    if OWNER_ID not in result["admin_ids"]:
        result["admin_ids"].append(OWNER_ID)

    return result


data = load_data()


# MA'LUMOTLARNI SAQLASH
def save_data():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# PAROLNI XESHLASH
def hash_password(password):
    salt = secrets.token_hex(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200000
    ).hex()

    return salt + ":" + hashed


# PAROLNI TEKSHIRISH
def check_password(password, stored):
    try:
        salt, saved_hash = stored.split(":", 1)

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200000
        ).hex()

        return secrets.compare_digest(candidate, saved_hash)

    except (ValueError, AttributeError):
        return False


# ADMIN TEKSHIRISH
def is_admin(update):
    return (
        update.effective_user is not None
        and update.effective_user.id in data["admin_ids"]
    )


# ADMIN PANEL MENYUSI
def menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "✍️ Xabar yozish",
                callback_data="message"
            ),
            InlineKeyboardButton(
                "⏱ Vaqt sozlash",
                callback_data="interval"
            )
        ],
        [
            InlineKeyboardButton(
                "▶️ Boshlash",
                callback_data="start"
            ),
            InlineKeyboardButton(
                "⏹ To‘xtatish",
                callback_data="stop"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Guruhlar",
                callback_data="groups"
            ),
            InlineKeyboardButton(
                "📊 Statistika",
                callback_data="stats"
            )
        ],
        [
            InlineKeyboardButton(
                "👑 Adminlar",
                callback_data="admins"
            )
        ],
        [
            InlineKeyboardButton(
                "🔒 Chiqish",
                callback_data="logout"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)
# ADMIN PANELGA KIRISH
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid == OWNER_ID:
        if context.user_data.get("authenticated"):
            await update.message.reply_text(
                "👑 Asosiy admin paneli",
                reply_markup=menu()
            )
            return

        context.user_data["awaiting_password"] = True

        await update.message.reply_text(
            "🔐 ASOSIY ADMIN KIRISH\n\nParolni kiriting:"
        )
        return

    if uid in data["admin_ids"]:
        if str(uid) not in data["admin_passwords"]:
            context.user_data["setting_admin_password"] = True

            await update.message.reply_text(
                "✅ Siz admin sifatida tasdiqlandingiz.\n\n"
                "🔐 O‘zingiz uchun yangi parol yarating "
                "(kamida 6 ta belgi):"
            )
        else:
            context.user_data["awaiting_admin_login"] = True

            await update.message.reply_text(
                "🔐 Admin paneliga kirish uchun "
                "shaxsiy parolingizni kiriting:"
            )
        return

    if str(uid) in data["pending_admins"]:
        await update.message.reply_text(
            "⏳ Adminlik so‘rovingiz yuborilgan. "
            "Asosiy admin tasdiqlashini kuting."
        )
        return

    data["pending_admins"][str(uid)] = {
        "name": user.full_name,
        "username": user.username or ""
    }

    save_data()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Tasdiqlash",
                callback_data=f"admin:approve:{uid}"
            ),
            InlineKeyboardButton(
                "❌ Rad etish",
                callback_data=f"admin:reject:{uid}"
            )
        ]
    ])

    username = f"@{user.username}" if user.username else "Username yo‘q"

    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=(
            "🔔 YANGI ADMIN SO‘ROVI\n\n"
            f"Ismi: {user.full_name}\n"
            f"Username: {username}\n"
            f"Telegram ID: {uid}\n\n"
            "Bu foydalanuvchini admin qilamizmi?"
        ),
        reply_markup=keyboard
    )

    await update.message.reply_text(
        "✅ So‘rovingiz asosiy adminga yuborildi."
    )


# BOT GURUHGA QO‘SHILGANDA
async def group_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    chat = update.my_chat_member.chat
    status = update.my_chat_member.new_chat_member.status

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


# GURUHLARGA XABAR YUBORISH
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
            print(f"Guruh xatosi {group_id}: {e}")


# ADMINLAR RO‘YXATI
async def show_admins(query):
    lines = ["👑 ADMINLAR RO‘YXATI\n"]
    keyboard = []

    for admin_id in data["admin_ids"]:
        if admin_id == OWNER_ID:
            lines.append(f"⭐ {admin_id} — Asosiy admin")
            continue

        lines.append(f"👤 {admin_id}")

        keyboard.append([
            InlineKeyboardButton(
                f"❌ {admin_id} ni chiqarish",
                callback_data=f"admin:remove:{admin_id}"
            )
        ])

    lines.append(
        f"\n⏳ Kutilayotgan so‘rovlar: "
        f"{len(data['pending_admins'])}"
    )

    keyboard.append([
        InlineKeyboardButton(
            "⬅️ Asosiy menyu",
            callback_data="back_menu"
        )
    ])

    await query.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
# TUGMALARNI BOSHQARISH
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    action = query.data

    # ADMIN SO‘ROVLARI
    if action.startswith("admin:"):

        if uid != OWNER_ID or not context.user_data.get("authenticated"):
            await query.message.reply_text(
                "⛔ Bu amal faqat asosiy admin uchun."
            )
            return

        parts = action.split(":")
        operation = parts[1]
        target_id = int(parts[2])

        # ADMINNI TASDIQLASH YOKI RAD ETISH
        if operation in ("approve", "reject"):

            pending = data["pending_admins"].get(str(target_id))

            if not pending:
                await query.message.reply_text(
                    "Bu so‘rov topilmadi yoki avval ko‘rib chiqilgan."
                )
                return

            if operation == "approve":

                if target_id not in data["admin_ids"]:
                    data["admin_ids"].append(target_id)

                data["pending_admins"].pop(str(target_id))
                save_data()

                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=(
                            "✅ Asosiy admin sizni tasdiqladi.\n"
                            "Endi /start yuboring va o‘zingiz uchun "
                            "shaxsiy parol yarating."
                        )
                    )
                except Exception as e:
                    print(f"Xabar yuborilmadi: {e}")

                await query.edit_message_text(
                    f"✅ {pending['name']} admin sifatida tasdiqlandi."
                )

            elif operation == "reject":

                data["pending_admins"].pop(str(target_id))
                save_data()

                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text="❌ Adminlik so‘rovingiz rad etildi."
                    )
                except Exception as e:
                    print(f"Xabar yuborilmadi: {e}")

                await query.edit_message_text(
                    f"❌ {pending['name']} so‘rovi rad etildi."
                )

            return

        # ADMINNI CHIQARISH
        elif operation == "remove":

            if target_id == OWNER_ID:
                await query.message.reply_text(
                    "⛔ Asosiy adminni chiqarib bo‘lmaydi."
                )
                return

            if target_id in data["admin_ids"]:

                data["admin_ids"].remove(target_id)
                data["admin_passwords"].pop(str(target_id), None)
                save_data()

                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text="⛔ Siz adminlikdan chiqarildingiz."
                    )
                except Exception as e:
                    print(f"Xabar yuborilmadi: {e}")

                await query.edit_message_text(
                    f"✅ {target_id} adminlikdan chiqarildi."
                )

            else:
                await query.message.reply_text(
                    "Bu foydalanuvchi admin emas."
                )

            return

    # ADMIN KIRISHINI TEKSHIRISH
    if not is_admin(update) or not context.user_data.get("authenticated"):
        await query.message.reply_text(
            "🔒 Avval admin sifatida parol bilan kiring."
        )
        return

    # CHIQISH
    if action == "logout":
        context.user_data.clear()

        await query.message.reply_text(
            "🔒 Tizimdan chiqdingiz. /start orqali qayta kiring."
        )

    # XABAR YOZISH
    elif action == "message":
        context.user_data["waiting"] = "message"

        await query.message.reply_text(
            "✍️ Xabar matnini yuboring:"
        )

    # VAQT SOZLASH
    elif action == "interval":
        context.user_data["waiting"] = "interval"

        await query.message.reply_text(
            "⏱ Intervalni soniyada kiriting. Masalan: 300"
        )

    # BOSHLASH
    elif action == "start":

        if not data["groups"] or not data["message"]:
            await query.message.reply_text(
                "❌ Guruh yoki xabar mavjud emas."
            )
            return

        if context.job_queue.get_jobs_by_name("broadcast"):
            await query.message.reply_text(
                "Bot allaqachon ishlayapti."
            )
            return

        context.job_queue.run_repeating(
            broadcast,
            interval=max(MIN_INTERVAL, int(data["interval"])),
            first=0,
            name="broadcast"
        )

        await query.message.reply_text(
            "▶️ Yuborish boshlandi!"
        )

    # TO‘XTATISH
    elif action == "stop":

        jobs = context.job_queue.get_jobs_by_name("broadcast")

        for job in jobs:
            job.schedule_removal()

        await query.message.reply_text(
            "⏹ Yuborish to‘xtatildi."
        )

    # GURUHLAR
    elif action == "groups":
        await query.message.reply_text(
            f"👥 Guruhlar soni: {len(data['groups'])}"
        )

    # STATISTIKA
    elif action == "stats":

        jobs = context.job_queue.get_jobs_by_name("broadcast")
        status = "Ishlayapti ✅" if jobs else "To‘xtatilgan ⏹"

        await query.message.reply_text(
            f"📊 STATISTIKA\n\n"
            f"Guruhlar: {len(data['groups'])}\n"
            f"Adminlar: {len(data['admin_ids'])}\n"
            f"Kutilayotgan so‘rovlar: {len(data['pending_admins'])}\n"
            f"Interval: {data['interval']} soniya\n"
            f"Holati: {status}"
        )

    # ADMINLAR
    elif action == "admins":

        if uid != OWNER_ID:
            await query.message.reply_text(
                "⛔ Adminlar ro‘yxatini faqat asosiy admin ko‘radi."
            )
            return

        await show_admins(query)

    # ASOSIY MENYU
    elif action == "back_menu":

        if uid != OWNER_ID:
            await query.message.reply_text("⛔ Ruxsat yo‘q.")
            return

        await query.message.reply_text(
            "👑 Asosiy admin paneli",
            reply_markup=menu()
        )
# FOYDALANUVCHILARDAN KELGAN XABARLAR
async def receive_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    uid = update.effective_user.id
    incoming_text = update.message.text

    # ASOSIY ADMIN PAROLI
    if uid == OWNER_ID and context.user_data.get("awaiting_password"):

        if incoming_text == ADMIN_PASSWORD:
            context.user_data["authenticated"] = True
            context.user_data.pop("awaiting_password", None)

            await update.message.reply_text(
                "✅ Parol to‘g‘ri!\n👑 Admin paneli ochildi.",
                reply_markup=menu()
            )
        else:
            await update.message.reply_text(
                "❌ Parol noto‘g‘ri."
            )

        return

    # YANGI ADMIN PAROL YARATISH
    if uid in data["admin_ids"] and uid != OWNER_ID:

        if context.user_data.get("setting_admin_password"):

            if len(incoming_text) < 6:
                await update.message.reply_text(
                    "❌ Parol kamida 6 ta belgidan iborat bo‘lsin."
                )
                return

            data["admin_passwords"][str(uid)] = hash_password(
                incoming_text
            )

            save_data()

            context.user_data.pop("setting_admin_password", None)
            context.user_data["authenticated"] = True

            try:
                await update.message.delete()
            except Exception:
                pass

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ Parolingiz yaratildi. Admin paneli ochildi.",
                reply_markup=menu()
            )

            return

        # ADMIN PAROLINI TEKSHIRISH
        if context.user_data.get("awaiting_admin_login"):

            stored = data["admin_passwords"].get(str(uid))

            if stored and check_password(incoming_text, stored):

                context.user_data.pop("awaiting_admin_login", None)
                context.user_data["authenticated"] = True

                try:
                    await update.message.delete()
                except Exception:
                    pass

                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="✅ Parol to‘g‘ri! Admin paneli ochildi.",
                    reply_markup=menu()
                )

            else:
                await update.message.reply_text(
                    "❌ Parol noto‘g‘ri. Qayta urinib ko‘ring."
                )

            return

    # ADMIN HUQUQINI TEKSHIRISH
    if not is_admin(update) or not context.user_data.get("authenticated"):
        return

    waiting = context.user_data.get("waiting")

    # XABARNI SAQLASH
    if waiting == "message":

        data["message"] = incoming_text
        save_data()

        context.user_data.pop("waiting", None)

        await update.message.reply_text(
            "✅ Xabar saqlandi!",
            reply_markup=menu()
        )

    # VAQTNI SAQLASH
    elif waiting == "interval":

        try:
            seconds = int(incoming_text)

            if seconds < MIN_INTERVAL:
                await update.message.reply_text(
                    "❌ Eng kam interval 60 soniya."
                )
                return

            data["interval"] = seconds
            save_data()

            context.user_data.pop("waiting", None)

            await update.message.reply_text(
                f"✅ Interval saqlandi: {seconds} soniya",
                reply_markup=menu()
            )

        except ValueError:
            await update.message.reply_text(
                "❌ Faqat raqam kiriting."
            )


# BOTNI ISHGA TUSHIRISH
def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(buttons)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            receive_text
        )
    )

    app.add_handler(
        ChatMemberHandler(
            group_member,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    print("BOT ISHGA TUSHDI!")

    app.run_polling()


if __name__ == "__main__":
    main()