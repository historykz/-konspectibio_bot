import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from database import Database

logging.basicConfig(format=’%(asctime)s - %(name)s - %(levelname)s - %(message)s’, level=logging.INFO)
logger = logging.getLogger(**name**)

BOT_TOKEN = os.getenv(‘BOT_TOKEN’)
ADMIN_IDS = list(map(int, os.getenv(‘ADMIN_IDS’, ‘’).split(’,’))) if os.getenv(‘ADMIN_IDS’) else []

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
await update.message.reply_text(‘Net dostupa. Obratites k administratoru.’)
return
hint = ‘\n\nVy administrator. /admin - panel upravleniya.’ if is_admin(user.id) else ‘’
await update.message.reply_text(’Privet, ’ + user.first_name + ‘!\n\nBot dlya konspektov.\n\n/list - spisok konspektov\n/get nomer - poluchit konspekt\nPrimer: /get 29’ + hint)

async def list_notes(update, context):
if not is_allowed(update.effective_user.id):
await update.message.reply_text(‘Net dostupa.’)
return
notes = db.get_all_notes()
if not notes:
await update.message.reply_text(‘Konspektov poka net.’)
return
lines = [‘Spisok konspektov:\n’]
for note_id, title in notes:
lines.append(str(note_id).zfill(2) + ’ - ’ + title)
lines.append(’\nPoluchit: /get nomer’)
await update.message.reply_text(’\n’.join(lines))

async def get_note(update, context):
if not is_allowed(update.effective_user.id):
await update.message.reply_text(‘Net dostupa.’)
return
if not context.args:
await update.message.reply_text(‘Ukazhite nomer. Primer: /get 29’)
return
try:
n = int(context.args[0])
except ValueError:
await update.message.reply_text(‘Nomer dolzhen byt chislom.’)
return
note = db.get_note(n)
if not note:
await update.message.reply_text(‘Konspekt ’ + str(n) + ’ ne najden. /list’)
return
note_id, title, file_id = note
await update.message.reply_document(document=file_id, caption=’Konspekt ’ + str(note_id).zfill(2) + ’\nTema: ’ + title)

ADMIN_KB = [
[InlineKeyboardButton(‘Spisok uchenikov’, callback_data=‘admin_users’), InlineKeyboardButton(‘Spisok konspektov’, callback_data=‘admin_notes’)],
[InlineKeyboardButton(‘Dobavit uchenika’, callback_data=‘admin_adduser’), InlineKeyboardButton(‘Udalit uchenika’, callback_data=‘admin_removeuser’)],
[InlineKeyboardButton(‘Zagruzit konspekt’, callback_data=‘admin_upload’), InlineKeyboardButton(‘Udalit konspekt’, callback_data=‘admin_deletenote’)],
]
BACK = [[InlineKeyboardButton(‘Nazad’, callback_data=‘admin_back’)]]

async def admin_panel(update, context):
if not is_admin(update.effective_user.id):
await update.message.reply_text(‘Tolko dlya administratorov.’)
return
await update.message.reply_text(‘Panel administratora\n\nVyberite dejstvie:’, reply_markup=InlineKeyboardMarkup(ADMIN_KB))

async def admin_callback(update, context):
query = update.callback_query
await query.answer()
aid = query.from_user.id
if not is_admin(aid):
await query.edit_message_text(‘Net dostupa.’)
return
d = query.data
if d == ‘admin_back’:
for x in [WAITING_UPLOAD, WAITING_ADD_USER, WAITING_REMOVE_USER, WAITING_DELETE_NOTE]:
x.pop(aid, None)
await query.edit_message_text(‘Panel administratora\n\nVyberite dejstvie:’, reply_markup=InlineKeyboardMarkup(ADMIN_KB))
elif d == ‘admin_users’:
users = db.get_all_users()
if not users:
text = ‘Ucheniki: pust.’
else:
lines = [‘Ucheniki (’ + str(len(users)) + ‘):\n’]
for uid, uname, fname in users:
lines.append(str(uid) + ’ - ’ + (’@’ + uname if uname else fname or ‘-’))
text = ‘\n’.join(lines)
await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK))
elif d == ‘admin_notes’:
notes = db.get_all_notes()
if not notes:
text = ‘Konspekty: pust.’
else:
lines = [‘Konspekty (’ + str(len(notes)) + ‘):\n’]
for nid, title in notes:
lines.append(str(nid).zfill(2) + ’ - ’ + title)
text = ‘\n’.join(lines)
await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK))
elif d == ‘admin_adduser’:
WAITING_ADD_USER[aid] = True
await query.edit_message_text(‘Dobavit uchenika\n\nOtpravte @username ili ID cherez probel:\nPrimer: @ivan @maria 123456’, reply_markup=InlineKeyboardMarkup(BACK))
elif d == ‘admin_removeuser’:
WAITING_REMOVE_USER[aid] = True
users = db.get_all_users()
if not users:
await query.edit_message_text(‘Pust.’, reply_markup=InlineKeyboardMarkup(BACK))
return
lines = [‘Udalit uchenika\n\nOtpravte @username ili ID:\n’]
for uid, uname, fname in users:
lines.append(str(uid) + ’ - ’ + (’@’ + uname if uname else fname or ‘-’))
await query.edit_message_text(’\n’.join(lines), reply_markup=InlineKeyboardMarkup(BACK))
elif d == ‘admin_upload’:
WAITING_UPLOAD[aid] = True
await query.edit_message_text(‘Zagruzit konspekt\n\nOtpravte PDF s podpisyu:\n29 Nazvanie temy\n\nPervoe slovo - nomer.’, reply_markup=InlineKeyboardMarkup(BACK))
elif d == ‘admin_deletenote’:
WAITING_DELETE_NOTE[aid] = True
notes = db.get_all_notes()
if not notes:
await query.edit_message_text(‘Konspektov net.’, reply_markup=InlineKeyboardMarkup(BACK))
return
lines = [‘Udalit konspekt\n\nOtpravte nomer:\n’]
for nid, title in notes:
lines.append(str(nid).zfill(2) + ’ - ’ + title)
await query.edit_message_text(’\n’.join(lines), reply_markup=InlineKeyboardMarkup(BACK))

async def handle_message(update, context):
uid = update.effective_user.id
msg = update.message
if is_admin(uid) and WAITING_UPLOAD.get(uid):
if msg.document and msg.document.mime_type == ‘application/pdf’:
cap = msg.caption or ‘’
parts = cap.strip().split(None, 1)
if len(parts) < 2:
await msg.reply_text(‘Format: 29 Nazvanie temy’)
return
try:
n = int(parts[0])
except ValueError:
await msg.reply_text(‘Pervoe slovo - nomer. Primer: 29 Tema’)
return
title = parts[1].strip()
fid = msg.document.file_id
if db.get_note(n):
db.update_note(n, title, fid)
status = ‘Konspekt obnovlen’
else:
db.add_note(n, title, fid)
status = ‘Konspekt dobavlen’
WAITING_UPLOAD.pop(uid, None)
await msg.reply_text(status + ‘!\n’ + str(n).zfill(2) + ’ - ’ + title)
else:
await msg.reply_text(‘Otpravte PDF s podpisyu: 29 Nazvanie temy’)
return
if is_admin(uid) and WAITING_ADD_USER.get(uid):
tokens = (msg.text or ‘’).replace(’\n’, ’ ‘).split()
added, failed = [], []
for t in tokens:
if t.startswith(’@’):
if db.add_user_by_username(t[1:]):
added.append(t)
else:
failed.append(t + ’ (est)’)
else:
try:
i = int(t)
if db.add_user_by_id(i):
added.append(‘ID ’ + str(i))
else:
failed.append(‘ID ’ + str(i) + ’ (est)’)
except ValueError:
failed.append(t + ’ (oshibka)’)
WAITING_ADD_USER.pop(uid, None)
lines = []
if added:
lines.append(‘Dobavleno (’ + str(len(added)) + ‘):’)
lines += [’  ’ + a for a in added]
if failed:
lines.append(‘Propushcheno:’)
lines += [’  ’ + f for f in failed]
await msg.reply_text(’\n’.join(lines) if lines else ‘Nichego ne raspoznano.’)
return
if is_admin(uid) and WAITING_REMOVE_USER.get(uid):
t = (msg.text or ‘’).strip()
if t.startswith(’@’):
ok = db.remove_user_by_username(t[1:])
label = t
else:
try:
i = int(t)
ok = db.remove_user_by_id(i)
label = ‘ID ’ + str(i)
except ValueError:
await msg.reply_text(‘Nevernyj format.’)
return
WAITING_REMOVE_USER.pop(uid, None)
await msg.reply_text(label + ’ udalon.’ if ok else label + ’ ne najden.’)
return
if is_admin(uid) and WAITING_DELETE_NOTE.get(uid):
try:
n = int((msg.text or ‘’).strip())
except ValueError:
await msg.reply_text(‘Vvedite chislo.’)
return
WAITING_DELETE_NOTE.pop(uid, None)
if db.get_note(n):
db.delete_note(n)
await msg.reply_text(‘Konspekt ’ + str(n).zfill(2) + ’ udalon.’)
else:
await msg.reply_text(‘Ne najden.’)
return
if not is_allowed(uid):
await msg.reply_text(‘Net dostupa.’)
return
await msg.reply_text(’/list - spisok\n/get nomer - poluchit konspekt’)

async def cmd_adduser(update, context):
if not is_admin(update.effective_user.id):
await update.message.reply_text(‘Tolko dlya admina.’)
return
if not context.args:
await update.message.reply_text(‘Primer: /adduser @ivan @maria 123456’)
return
added, failed = [], []
for t in context.args:
if t.startswith(’@’):
if db.add_user_by_username(t[1:]):
added.append(t)
else:
failed.append(t + ’ (est)’)
else:
try:
i = int(t)
if db.add_user_by_id(i):
added.append(‘ID ’ + str(i))
else:
failed.append(‘ID ’ + str(i) + ’ (est)’)
except ValueError:
failed.append(t + ’ (oshibka)’)
lines = []
if added:
lines.append(‘Dobavleno:’)
lines += [’  ’ + a for a in added]
if failed:
lines.append(‘Propushcheno:’)
lines += [’  ’ + f for f in failed]
await update.message.reply_text(’\n’.join(lines) if lines else ‘Nichego.’)

async def cmd_removeuser(update, context):
if not is_admin(update.effective_user.id):
await update.message.reply_text(‘Tolko dlya admina.’)
return
if not context.args:
await update.message.reply_text(‘Primer: /removeuser @ivan’)
return
t = context.args[0].strip()
if t.startswith(’@’):
ok = db.remove_user_by_username(t[1:])
label = t
else:
try:
i = int(t)
ok = db.remove_user_by_id(i)
label = ‘ID ’ + str(i)
except ValueError:
await update.message.reply_text(‘Nevernyj format.’)
return
await update.message.reply_text(label + ’ udalon.’ if ok else label + ’ ne najden.’)

async def cmd_users(update, context):
if not is_admin(update.effective_user.id):
await update.message.reply_text(‘Tolko dlya admina.’)
return
users = db.get_all_users()
if not users:
await update.message.reply_text(‘Spisok pust.’)
return
lines = [‘Ucheniki (’ + str(len(users)) + ‘):\n’]
for uid2, uname, fname in users:
lines.append(str(uid2) + ’ - ’ + (’@’ + uname if uname else fname or ‘-’))
await update.message.reply_text(’\n’.join(lines))

async def help_cmd(update, context):
if not is_allowed(update.effective_user.id):
await update.message.reply_text(‘Net dostupa.’)
return
if is_admin(update.effective_user.id):
text = ‘/admin - panel\n/adduser @u1 @u2 - dobavit\n/removeuser @u - udalit\n/users - spisok\n/list - konspekty\n/get nomer - poluchit’
else:
text = ‘/list - spisok konspektov\n/get nomer - poluchit\nPrimer: /get 29’
await update.message.reply_text(text)

def main():
if not BOT_TOKEN:
raise ValueError(‘BOT_TOKEN ne zadan!’)
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler(‘start’, start))
app.add_handler(CommandHandler(‘help’, help_cmd))
app.add_handler(CommandHandler(‘list’, list_notes))
app.add_handler(CommandHandler(‘get’, get_note))
app.add_handler(CommandHandler(‘admin’, admin_panel))
app.add_handler(CommandHandler(‘adduser’, cmd_adduser))
app.add_handler(CommandHandler(‘removeuser’, cmd_removeuser))
app.add_handler(CommandHandler(‘users’, cmd_users))
app.add_handler(CallbackQueryHandler(admin_callback))
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
logger.info(‘Bot zapushchen!’)
app.run_polling(allowed_updates=Update.ALL_TYPES)

if **name** == ‘**main**’:
main()
