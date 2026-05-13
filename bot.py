import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
Application, CommandHandler, MessageHandler,
CallbackQueryHandler, ContextTypes, filters
)
from database import Database

logging.basicConfig(format=”%(asctime)s - %(name)s - %(levelname)s - %(message)s”, level=logging.INFO)
logger = logging.getLogger(**name**)

BOT_TOKEN = os.getenv(“BOT_TOKEN”)
ADMIN_IDS = list(map(int, os.getenv(“ADMIN_IDS”, “”).split(”,”))) if os.getenv(“ADMIN_IDS”) else []

db = Database()

WAITING_UPLOAD = {}
WAITING_ADD_USER = {}
WAITING_REMOVE_USER = {}
WAITING_DELETE_NOTE = {}

def is_admin(user_id):
return user_id in ADMIN_IDS

def is_allowed(user_id):
return db.user_exists(user_id) or is_admin(user_id)

async def start(update, context):
user = update.effective_user
if not is_allowed(user.id):
await update.message.reply_text(“U v?? net dostupa k botu.\nObratites k administratoru.”)
return
admin_hint = “\n\nVy administrator. Vvedite /admin dlya paneli upravleniya.” if is_admin(user.id) else “”
await update.message.reply_text(
“Privet, “ + user.first_name + “!\n\nEto bot dlya polucheniya konspektov.\n\nKomandy:\n/list - spisok konspektov\n/get nomer - poluchit konspekt\nPrimer: /get 29” + admin_hint
)

async def list_notes(update, context):
user = update.effective_user
if not is_allowed(user.id):
await update.message.reply_text(“Net dostupa.”)
return
notes = db.get_all_notes()
if not notes:
await update.message.reply_text(“Konspektov poka net.”)
return
lines = [“Spisok konspektov:\n”]
for note_id, title in notes:
lines.append(str(note_id).zfill(2) + “ - “ + title)
lines.append(”\nChtoby poluchit: /get nomer”)
await update.message.reply_text(”\n”.join(lines))

async def get_note(update, context):
user = update.effective_user
if not is_allowed(user.id):
await update.message.reply_text(“Net dostupa.”)
return
if not context.args:
await update.message.reply_text(“Ukazhite nomer. Primer: /get 29”)
return
try:
note_number = int(context.args[0])
except ValueError:
await update.message.reply_text(“Nomer dolzhen byt chislom. Primer: /get 29”)
return
note = db.get_note(note_number)
if not note:
await update.message.reply_text(“Konspekt “ + str(note_number) + “ ne najden. Spisok: /list”)
return
note_id, title, file_id = note
await update.message.reply_document(
document=file_id,
caption=“Konspekt “ + str(note_id).zfill(2) + “\nTema: “ + title
)

async def admin_panel(update, context):
if not is_admin(update.effective_user.id):
await update.message.reply_text(“Tolko dlya administratorov.”)
return
keyboard = [
[InlineKeyboardButton(“Spisok uchenikov”, callback_data=“admin_users”),
InlineKeyboardButton(“Spisok konspektov”, callback_data=“admin_notes”)],
[InlineKeyboardButton(“Dobavit uchenika”, callback_data=“admin_adduser”),
InlineKeyboardButton(“Udalit uchenika”, callback_data=“admin_removeuser”)],
[InlineKeyboardButton(“Zagruzit konspekt”, callback_data=“admin_upload”),
InlineKeyboardButton(“Udalit konspekt”, callback_data=“admin_deletenote”)],
]
await update.message.reply_text(
“Panel administratora\n\nVyberite dejstvie:”,
reply_markup=InlineKeyboardMarkup(keyboard)
)

BACK_BTN = [[InlineKeyboardButton(“Nazad”, callback_data=“admin_back”)]]

async def admin_callback(update, context):
query = update.callback_query
await query.answer()
admin_id = query.from_user.id

```
if not is_admin(admin_id):
    await query.edit_message_text("Net dostupa.")
    return

data = query.data

if data == "admin_back":
    for d in [WAITING_UPLOAD, WAITING_ADD_USER, WAITING_REMOVE_USER, WAITING_DELETE_NOTE]:
        d.pop(admin_id, None)
    keyboard = [
        [InlineKeyboardButton("Spisok uchenikov", callback_data="admin_users"),
         InlineKeyboardButton("Spisok konspektov", callback_data="admin_notes")],
        [InlineKeyboardButton("Dobavit uchenika", callback_data="admin_adduser"),
         InlineKeyboardButton("Udalit uchenika", callback_data="admin_removeuser")],
        [InlineKeyboardButton("Zagruzit konspekt", callback_data="admin_upload"),
         InlineKeyboardButton("Udalit konspekt", callback_data="admin_deletenote")],
    ]
    await query.edit_message_text("Panel administratora\n\nVyberite dejstvie:", reply_markup=InlineKeyboardMarkup(keyboard))

elif data == "admin_users":
    users = db.get_all_users()
    if not users:
        text = "Ucheniki: spisok pust."
    else:
        lines = ["Ucheniki (" + str(len(users)) + "):\n"]
        for uid, username, first_name in users:
            name = "@" + username if username else (first_name or "-")
            lines.append(str(uid) + " - " + name)
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_BTN))

elif data == "admin_notes":
    notes = db.get_all_notes()
    if not notes:
        text = "Konspekty: spisok pust."
    else:
        lines = ["Konspekty (" + str(len(notes)) + "):\n"]
        for note_id, title in notes:
            lines.append(str(note_id).zfill(2) + " - " + title)
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_BTN))

elif data == "admin_adduser":
    WAITING_ADD_USER[admin_id] = True
    await query.edit_message_text(
        "Dobavit uchenika\n\nOtpravte @username ili ID cherez probel:\nPrimer: @ivan @maria 123456",
        reply_markup=InlineKeyboardMarkup(BACK_BTN)
    )

elif data == "admin_removeuser":
    WAITING_REMOVE_USER[admin_id] = True
    users = db.get_all_users()
    if not users:
        await query.edit_message_text("Spisok pust.", reply_markup=InlineKeyboardMarkup(BACK_BTN))
        return
    lines = ["Udalit uchenika\n\nOtpravte @username ili ID:\n"]
    for uid, username, first_name in users:
        name = "@" + username if username else (first_name or "-")
        lines.append(str(uid) + " - " + name)
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(BACK_BTN))

elif data == "admin_upload":
    WAITING_UPLOAD[admin_id] = True
    await query.edit_message_text(
        "Zagruzit konspekt\n\nOtpravte PDF fajl s podpisyu:\n29 Nazvanie temy\n\nPrimer podpisi:\n29 Fotosintez i ego stadii\n\nPervoe slovo - nomer konspekta.",
        reply_markup=InlineKeyboardMarkup(BACK_BTN)
    )

elif data == "admin_deletenote":
    WAITING_DELETE_NOTE[admin_id] = True
    notes = db.get_all_notes()
    if not notes:
        await query.edit_message_text("Konspektov net.", reply_markup=InlineKeyboardMarkup(BACK_BTN))
        return
    lines = ["Udalit konspekt\n\nOtpravte nomer:\n"]
    for note_id, title in notes:
        lines.append(str(note_id).zfill(2) + " - " + title)
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(BACK_BTN))
```

async def handle_message(update, context):
user = update.effective_user
user_id = user.id
message = update.message

```
if is_admin(user_id) and WAITING_UPLOAD.get(user_id):
    if message.document and message.document.mime_type == "application/pdf":
        caption = message.caption or ""
        parts = caption.strip().split(None, 1)
        if len(parts) < 2:
            await message.reply_text("Format podpisi: 29 Nazvanie temy")
            return
        try:
            note_number = int(parts[0])
        except ValueError:
            await message.reply_text("Pervoe slovo dolzhno byt nomerom. Primer: 29 Tema")
            return
        title = parts[1].strip()
        file_id = message.document.file_id
        existing = db.get_note(note_number)
        if existing:
            db.update_note(note_number, title, file_id)
            status = "Konspekt obnovlen"
        else:
            db.add_note(note_number, title, file_id)
            status = "Konspekt dobavlen"
        WAITING_UPLOAD.pop(user_id, None)
        await message.reply_text(status + "!\n\n" + str(note_number).zfill(2) + " - " + title)
    else:
        await message.reply_text("Otpravte PDF fajl s podpisyu: 29 Nazvanie temy")
    return

if is_admin(user_id) and WAITING_ADD_USER.get(user_id):
    tokens = (message.text or "").replace("\n", " ").split()
    added, failed = [], []
    for token in tokens:
        if token.startswith("@"):
            username = token[1:]
            if db.add_user_by_username(username):
                added.append("@" + username)
            else:
                failed.append("@" + username + " (uzhe est)")
        else:
            try:
                uid = int(token)
                if db.add_user_by_id(uid):
                    added.append("ID " + str(uid))
                else:
                    failed.append("ID " + str(uid) + " (uzhe est)")
            except ValueError:
                failed.append(token + " (nevernyj format)")
    WAITING_ADD_USER.pop(user_id, None)
    lines = []
    if added:
        lines.append("Dobavleno (" + str(len(added)) + "):")
        lines += ["  " + a for a in added]
    if failed:
        lines.append("Propushcheno (" + str(len(failed)) + "):")
        lines += ["  " + f for f in failed]
    if not lines:
        lines = ["Ne udalos raspoznat ni odnogo polzovatelya."]
    await message.reply_text("\n".join(lines))
    return

if is_admin(user_id) and WAITING_REMOVE_USER.get(user_id):
    text = (message.text or "").strip()
    if text.startswith("@"):
        username = text[1:]
        removed = db.remove_user_by_username(username)
        label = "@" + username
    else:
        try:
            uid = int(text)
            removed = db.remove_user_by_id(uid)
            label = "ID " + str(uid)
        except ValueError:
            await message.reply_text("Nevernyj format.")
            return
    WAITING_REMOVE_USER.pop(user_id, None)
    await message.reply_text(label + " udalon." if removed else label + " ne najden.")
    return

if is_admin(user_id) and WAITING_DELETE_NOTE.get(user_id):
    text = (message.text or "").strip()
    try:
        note_number = int(text)
    except ValueError:
        await message.reply_text("Vvedite nomer konspekta (chislo).")
        return
    note = db.get_note(note_number)
    WAITING_DELETE_NOTE.pop(user_id, None)
    if note:
        db.delete_note(note_number)
        await message.reply_text("Konspekt " + str(note_number).zfill(2) + " udalon.")
    else:
        await message.reply_text("Konspekt " + str(note_number) + " ne najden.")
    return

if not is_allowed(user_id):
    await message.reply_text("Net dostupa.")
    return

await message.reply_text("Komandy:\n/list - spisok konspektov\n/get nomer - poluchit konspekt")
```

async def cmd_adduser(update, context):
if not is_admin(update.effective_user.id):
await update.message.reply_text(“Tolko dlya administratorov.”)
return
if not context.args:
await update.message.reply_text(“Primer: /adduser @ivan @maria 123456”)
return
added, failed = [], []
for token in context.args:
if token.startswith(”@”):
username = token[1:]
if db.add_user_by_username(username):
added.append(”@” + username)
else:
failed.append(”@” + username + “ (uzhe est)”)
else:
try:
uid = int(token)
if db.add_user_by_id(uid):
added.append(“ID “ + str(uid))
else:
failed.append(“ID “ + str(uid) + “ (uzhe est)”)
except ValueError:
failed.append(token + “ (nevernyj format)”)
lines = []
if added:
lines.append(“Dobavleno (” + str(len(added)) + “):”)
lines += [”  “ + a for a in added]
if failed:
lines.append(“Propushcheno:”)
lines += [”  “ + f for f in failed]
await update.message.reply_text(”\n”.join(lines))

async def cmd_removeuser(update, context):
if not is_admin(update.effective_user.id):
await update.message.reply_text(“Tolko dlya administratorov.”)
return
if not context.args:
await update.message.reply_text(“Primer: /removeuser @ivan”)
return
token = context.args[0].strip()
if token.startswith(”@”):
removed = db.remove_user_by_username(token[1:])
label = token
else:
try:
uid = int(token)
removed = db.remove_user_by_id(uid)
label = “ID “ + str(uid)
except ValueError:
await update.message.reply_text(“Nevernyj format.”)
return
await update.message.reply_text(label + “ udalon.” if removed else label + “ ne najden.”)

async def cmd_users(update, context):
if not is_admin(update.effective_user.id):
await update.message.reply_text(“Tolko dlya administratorov.”)
return
users = db.get_all_users()
if not users:
await update.message.reply_text(“Spisok uchenikov pust.”)
return
lines = [“Ucheniki (” + str(len(users)) + “):\n”]
for uid, username, first_name in users:
name = “@” + username if username else (first_name or “-”)
lines.append(str(uid) + “ - “ + name)
await update.message.reply_text(”\n”.join(lines))

async def help_cmd(update, context):
user = update.effective_user
if not is_allowed(user.id):
await update.message.reply_text(“Net dostupa.”)
return
if is_admin(user.id):
text = “Komandy administratora:\n\n/admin - panel upravleniya\n/adduser @u1 @u2 - dobavit uchenikov\n/removeuser @u - udalit uchenika\n/users - spisok uchenikov\n/list - spisok konspektov\n/get nomer - poluchit konspekt”
else:
text = “Komandy:\n\n/list - spisok konspektov\n/get nomer - poluchit konspekt\nPrimer: /get 29”
await update.message.reply_text(text)

def main():
if not BOT_TOKEN:
raise ValueError(“BOT_TOKEN ne zadan!”)
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler(“start”, start))
app.add_handler(CommandHandler(“help”, help_cmd))
app.add_handler(CommandHandler(“list”, list_notes))
app.add_handler(CommandHandler(“get”, get_note))
app.add_handler(CommandHandler(“admin”, admin_panel))
app.add_handler(CommandHandler(“adduser”, cmd_adduser))
app.add_handler(CommandHandler(“removeuser”, cmd_removeuser))
app.add_handler(CommandHandler(“users”, cmd_users))
app.add_handler(CallbackQueryHandler(admin_callback))
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
logger.info(“Bot zapushchen!”)
app.run_polling(allowed_updates=Update.ALL_TYPES)

if **name** == “**main**”:
main()
