import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
Application, CommandHandler, MessageHandler,
CallbackQueryHandler, ContextTypes, filters
)
from database import Database

logging.basicConfig(
format=”%(asctime)s - %(name)s - %(levelname)s - %(message)s”,
level=logging.INFO
)
logger = logging.getLogger(**name**)

BOT_TOKEN = os.getenv(“BOT_TOKEN”)
ADMIN_IDS = list(map(int, os.getenv(“ADMIN_IDS”, “”).split(”,”))) if os.getenv(“ADMIN_IDS”) else []

db = Database()

WAITING_UPLOAD = {}
WAITING_ADD_USER = {}
WAITING_REMOVE_USER = {}
WAITING_DELETE_NOTE = {}

def is_admin(user_id: int) -> bool:
return user_id in ADMIN_IDS

def is_allowed(user_id: int) -> bool:
return db.user_exists(user_id) or is_admin(user_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
user = update.effective_user
if not is_allowed(user.id):
await update.message.reply_text(“⛔ У вас нет доступа к боту.\nОбратитесь к администратору.”)
return
admin_hint = “\n\n🔧 <b>Вы администратор.</b> Введите /admin для панели управления.” if is_admin(user.id) else “”
await update.message.reply_text(
f”👋 Привет, <b>{user.first_name}</b>!\n\n”
f”📚 Это бот для получения конспектов.\n\n”
f”<b>Команды:</b>\n”
f”• /list — список всех конспектов\n”
f”• /get <номер> — получить конспект\n”
f”  Пример: <code>/get 29</code>{admin_hint}”,
parse_mode=“HTML”
)

async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
user = update.effective_user
if not is_allowed(user.id):
await update.message.reply_text(“⛔ У вас нет доступа.”)
return
notes = db.get_all_notes()
if not notes:
await update.message.reply_text(“📭 Конспектов пока нет.”)
return
lines = [“📚 <b>Список конспектов:</b>\n”]
for note_id, title in notes:
lines.append(f”• <code>{note_id:02d}</code> — {title}”)
lines.append(”\n✏️ Чтобы получить: <code>/get <номер></code>”)
await update.message.reply_text(”\n”.join(lines), parse_mode=“HTML”)

async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
user = update.effective_user
if not is_allowed(user.id):
await update.message.reply_text(“⛔ У вас нет доступа.”)
return
if not context.args:
await update.message.reply_text(“❗ Укажите номер конспекта.\nПример: <code>/get 29</code>”, parse_mode=“HTML”)
return
try:
note_number = int(context.args[0])
except ValueError:
await update.message.reply_text(“❗ Номер должен быть числом. Пример: <code>/get 29</code>”, parse_mode=“HTML”)
return
note = db.get_note(note_number)
if not note:
await update.message.reply_text(f”❌ Конспект №{note_number} не найден.\nСписок: /list”)
return
note_id, title, file_id = note
await update.message.reply_document(
document=file_id,
caption=f”📄 <b>Конспект №{note_id:02d}</b>\n📌 <b>Тема:</b> {title}”,
parse_mode=“HTML”
)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update.effective_user.id):
await update.message.reply_text(“⛔ Только для администраторов.”)
return
keyboard = [
[InlineKeyboardButton(“👥 Список учеников”, callback_data=“admin_users”),
InlineKeyboardButton(“📚 Список конспектов”, callback_data=“admin_notes”)],
[InlineKeyboardButton(“➕ Добавить ученика”, callback_data=“admin_adduser”),
InlineKeyboardButton(“❌ Удалить ученика”, callback_data=“admin_removeuser”)],
[InlineKeyboardButton(“📤 Загрузить конспект”, callback_data=“admin_upload”),
InlineKeyboardButton(“🗑 Удалить конспект”, callback_data=“admin_deletenote”)],
]
await update.message.reply_text(
“🔧 <b>Панель администратора</b>\n\nВыберите действие:”,
reply_markup=InlineKeyboardMarkup(keyboard),
parse_mode=“HTML”
)

ADMIN_KEYBOARD = [
[InlineKeyboardButton(“👥 Список учеников”, callback_data=“admin_users”),
InlineKeyboardButton(“📚 Список конспектов”, callback_data=“admin_notes”)],
[InlineKeyboardButton(“➕ Добавить ученика”, callback_data=“admin_adduser”),
InlineKeyboardButton(“❌ Удалить ученика”, callback_data=“admin_removeuser”)],
[InlineKeyboardButton(“📤 Загрузить конспект”, callback_data=“admin_upload”),
InlineKeyboardButton(“🗑 Удалить конспект”, callback_data=“admin_deletenote”)],
]
BACK_BTN = [[InlineKeyboardButton(“◀️ Назад”, callback_data=“admin_back”)]]

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()
admin_id = query.from_user.id

```
if not is_admin(admin_id):
    await query.edit_message_text("⛔ Нет доступа.")
    return

data = query.data

if data == "admin_back":
    for d in [WAITING_UPLOAD, WAITING_ADD_USER, WAITING_REMOVE_USER, WAITING_DELETE_NOTE]:
        d.pop(admin_id, None)
    await query.edit_message_text(
        "🔧 <b>Панель администратора</b>\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(ADMIN_KEYBOARD),
        parse_mode="HTML"
    )

elif data == "admin_users":
    users = db.get_all_users()
    if not users:
        text = "👥 <b>Ученики:</b>\nСписок пуст."
    else:
        lines = [f"👥 <b>Ученики ({len(users)}):</b>\n"]
        for uid, username, first_name in users:
            name = f"@{username}" if username else (first_name or "—")
            lines.append(f"• <code>{uid}</code> — {name}")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(BACK_BTN))

elif data == "admin_notes":
    notes = db.get_all_notes()
    if not notes:
        text = "📚 <b>Конспекты:</b>\nСписок пуст."
    else:
        lines = [f"📚 <b>Конспекты ({len(notes)}):</b>\n"]
        for note_id, title in notes:
            lines.append(f"• <code>{note_id:02d}</code> — {title}")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(BACK_BTN))

elif data == "admin_adduser":
    WAITING_ADD_USER[admin_id] = True
    await query.edit_message_text(
        "➕ <b>Добавить ученика(ов)</b>\n\n"
        "Отправьте одного или нескольких через пробел / новую строку:\n\n"
        "<b>Форматы:</b>\n"
        "• <code>@username</code>\n"
        "• <code>123456789</code> (Telegram ID)\n\n"
        "<b>Пример массово:</b>\n"
        "<code>@ivan @maria @dmitry</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(BACK_BTN)
    )

elif data == "admin_removeuser":
    WAITING_REMOVE_USER[admin_id] = True
    users = db.get_all_users()
    if not users:
        await query.edit_message_text("👥 Список пуст.", reply_markup=InlineKeyboardMarkup(BACK_BTN))
        return
    lines = ["❌ <b>Удалить ученика</b>\n\nОтправьте @username или ID:\n"]
    for uid, username, first_name in users:
        name = f"@{username}" if username else (first_name or "—")
        lines.append(f"• <code>{uid}</code> — {name}")
    await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(BACK_BTN))

elif data == "admin_upload":
    WAITING_UPLOAD[admin_id] = True
    await query.edit_message_text(
        "📤 <b>Загрузить конспект</b>\n\n"
        "Отправьте PDF файл с подписью:\n"
        "<code>29 Название темы</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>29 Фотосинтез и его стадии</code>\n\n"
        "⚠️ Первое слово — номер конспекта.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(BACK_BTN)
    )

elif data == "admin_deletenote":
    WAITING_DELETE_NOTE[admin_id] = True
    notes = db.get_all_notes()
    if not notes:
        await query.edit_message_text("📚 Конспектов нет.", reply_markup=InlineKeyboardMarkup(BACK_BTN))
        return
    lines = ["🗑 <b>Удалить конспект</b>\n\nОтправьте номер:\n"]
    for note_id, title in notes:
        lines.append(f"• <code>{note_id:02d}</code> — {title}")
    await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(BACK_BTN))
```

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
user = update.effective_user
user_id = user.id
message = update.message

```
# ── Загрузка PDF ──
if is_admin(user_id) and WAITING_UPLOAD.get(user_id):
    if message.document and message.document.mime_type == "application/pdf":
        caption = message.caption or ""
        parts = caption.strip().split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("❗ Формат подписи: <code>29 Название темы</code>", parse_mode="HTML")
            return
        try:
            note_number = int(parts[0])
        except ValueError:
            await message.reply_text("❗ Первое слово должно быть номером. Пример: <code>29 Тема</code>", parse_mode="HTML")
            return
        title = parts[1].strip()
        file_id = message.document.file_id
        existing = db.get_note(note_number)
        if existing:
            db.update_note(note_number, title, file_id)
            status = "♻️ Конспект обновлён"
        else:
            db.add_note(note_number, title, file_id)
            status = "✅ Конспект добавлен"
        WAITING_UPLOAD.pop(user_id, None)
        await message.reply_text(f"{status}!\n\n📄 <b>№{note_number:02d}</b> — {title}", parse_mode="HTML")
    else:
        await message.reply_text("❗ Отправьте PDF файл с подписью: <code>29 Название темы</code>", parse_mode="HTML")
    return

# ── Добавить учеников ──
if is_admin(user_id) and WAITING_ADD_USER.get(user_id):
    tokens = (message.text or "").replace("\n", " ").split()
    added, failed = [], []
    for token in tokens:
        if token.startswith("@"):
            username = token[1:]
            if db.add_user_by_username(username):
                added.append(f"@{username}")
            else:
                failed.append(f"@{username} (уже есть)")
        else:
            try:
                uid = int(token)
                if db.add_user_by_id(uid):
                    added.append(f"ID {uid}")
                else:
                    failed.append(f"ID {uid} (уже есть)")
            except ValueError:
                failed.append(f"{token} (неверный формат)")
    WAITING_ADD_USER.pop(user_id, None)
    lines = []
    if added:
        lines.append(f"✅ <b>Добавлено ({len(added)}):</b>")
        lines += [f"  • {a}" for a in added]
    if failed:
        lines.append(f"\n⚠️ <b>Пропущено ({len(failed)}):</b>")
        lines += [f"  • {f}" for f in failed]
    if not lines:
        lines = ["❗ Не удалось распознать ни одного пользователя."]
    await message.reply_text("\n".join(lines), parse_mode="HTML")
    return

# ── Удалить ученика ──
if is_admin(user_id) and WAITING_REMOVE_USER.get(user_id):
    text = (message.text or "").strip()
    if text.startswith("@"):
        username = text[1:]
        removed = db.remove_user_by_username(username)
        label = f"@{username}"
    else:
        try:
            uid = int(text)
            removed = db.remove_user_by_id(uid)
            label = f"ID {uid}"
        except ValueError:
            await message.reply_text("❗ Неверный формат. Отправьте @username или ID.")
            return
    WAITING_REMOVE_USER.pop(user_id, None)
    await message.reply_text(f"✅ Ученик {label} удалён." if removed else f"❌ Ученик {label} не найден.")
    return

# ── Удалить конспект ──
if is_admin(user_id) and WAITING_DELETE_NOTE.get(user_id):
    text = (message.text or "").strip()
    try:
        note_number = int(text)
    except ValueError:
        await message.reply_text("❗ Введите номер конспекта (число).")
        return
    note = db.get_note(note_number)
    WAITING_DELETE_NOTE.pop(user_id, None)
    if note:
        db.delete_note(note_number)
        await message.reply_text(f"✅ Конспект №{note_number:02d} удалён.")
    else:
        await message.reply_text(f"❌ Конспект №{note_number} не найден.")
    return

# ── Обычный пользователь ──
if not is_allowed(user_id):
    await message.reply_text("⛔ У вас нет доступа.")
    return

await message.reply_text(
    "Используйте команды:\n• /list — список конспектов\n• /get &lt;номер&gt; — получить конспект",
    parse_mode="HTML"
)
```

async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update.effective_user.id):
await update.message.reply_text(“⛔ Только для администраторов.”)
return
if not context.args:
await update.message.reply_text(“❗ Пример: <code>/adduser @ivan @maria 123456</code>”, parse_mode=“HTML”)
return
added, failed = [], []
for token in context.args:
if token.startswith(”@”):
username = token[1:]
if db.add_user_by_username(username):
added.append(f”@{username}”)
else:
failed.append(f”@{username} (уже есть)”)
else:
try:
uid = int(token)
if db.add_user_by_id(uid):
added.append(f”ID {uid}”)
else:
failed.append(f”ID {uid} (уже есть)”)
except ValueError:
failed.append(f”{token} (неверный формат)”)
lines = []
if added:
lines.append(f”✅ <b>Добавлено ({len(added)}):</b>”)
lines += [f”  • {a}” for a in added]
if failed:
lines.append(f”\n⚠️ <b>Пропущено:</b>”)
lines += [f”  • {f}” for f in failed]
await update.message.reply_text(”\n”.join(lines), parse_mode=“HTML”)

async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update.effective_user.id):
await update.message.reply_text(“⛔ Только для администраторов.”)
return
if not context.args:
await update.message.reply_text(“❗ Пример: <code>/removeuser @ivan</code>”, parse_mode=“HTML”)
return
token = context.args[0].strip()
if token.startswith(”@”):
removed = db.remove_user_by_username(token[1:])
label = token
else:
try:
uid = int(token)
removed = db.remove_user_by_id(uid)
label = f”ID {uid}”
except ValueError:
await update.message.reply_text(“❗ Неверный формат.”)
return
await update.message.reply_text(f”✅ {label} удалён.” if removed else f”❌ {label} не найден.”)

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update.effective_user.id):
await update.message.reply_text(“⛔ Только для администраторов.”)
return
users = db.get_all_users()
if not users:
await update.message.reply_text(“👥 Список учеников пуст.”)
return
lines = [f”👥 <b>Ученики ({len(users)}):</b>\n”]
for uid, username, first_name in users:
name = f”@{username}” if username else (first_name or “—”)
lines.append(f”• <code>{uid}</code> — {name}”)
await update.message.reply_text(”\n”.join(lines), parse_mode=“HTML”)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
user = update.effective_user
if not is_allowed(user.id):
await update.message.reply_text(“⛔ У вас нет доступа.”)
return
if is_admin(user.id):
text = (
“🔧 <b>Команды администратора:</b>\n\n”
“/admin — панель управления\n”
“/adduser @u1 @u2 — добавить учеников\n”
“/removeuser @u — удалить ученика\n”
“/users — список учеников\n”
“/list — список конспектов\n”
“/get <номер> — получить конспект\n\n”
“📤 <b>Загрузка:</b> /admin → Загрузить конспект\n”
“Подпись к PDF: <code>29 Тема</code>”
)
else:
text = (
“📚 <b>Команды:</b>\n\n”
“/list — список конспектов\n”
“/get <номер> — получить конспект\n”
“Пример: <code>/get 29</code>”
)
await update.message.reply_text(text, parse_mode=“HTML”)

def main():
if not BOT_TOKEN:
raise ValueError(“BOT_TOKEN не задан!”)
if not ADMIN_IDS:
logger.warning(“ADMIN_IDS не задан!”)

```
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("list", list_notes))
app.add_handler(CommandHandler("get", get_note))
app.add_handler(CommandHandler("admin", admin_panel))
app.add_handler(CommandHandler("adduser", cmd_adduser))
app.add_handler(CommandHandler("removeuser", cmd_removeuser))
app.add_handler(CommandHandler("users", cmd_users))
app.add_handler(CallbackQueryHandler(admin_callback))
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

logger.info("Бот запущен!")
app.run_polling(allowed_updates=Update.ALL_TYPES)
```

if **name** == “**main**”:
main()
