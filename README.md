# 📘 Telegram-бот для выдачи PDF-конспектов

Telegram-бот, который выдаёт PDF-конспекты ученикам по номеру.
Стек: **Python 3.11**, **aiogram 3**, **SQLite (aiosqlite)**.

---

## 🧠 Что умеет бот

### Ученик
- `/start` — приветствие
- Пишет номер конспекта (например `29`) → получает PDF + тему
- `/list` — список доступных конспектов

### Админ (только `ADMIN_ID` из `.env`)
- Загрузка PDF: отправляет файл → бот спрашивает номер → потом тему → сохраняет
- Если номер уже занят — бот предлагает заменить кнопкой ✅/❌
- `/add_student 123456789` или `/add_student @username`
- `/add_students @u1 @u2 123456789` — массово
- `/remove_student <id|@username>`
- `/students` — список учеников
- `/notes` — список конспектов
- `/delete_note 29` — удалить конспект

---

## 📂 Структура проекта

```
telegram-notes-bot/
├── files/                  # сюда сохраняются PDF (создаётся автоматически)
├── handlers/
│   ├── __init__.py
│   ├── admin.py
│   └── user.py
├── config.py
├── database.py
├── keyboards.py
├── main.py
├── utils.py
├── requirements.txt
├── Procfile                # для Railway
├── runtime.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 🚀 Шаг 1 — Создаём бота в BotFather

1. Откройте Telegram, найдите [@BotFather](https://t.me/BotFather).
2. Отправьте `/newbot`.
3. Придумайте имя (например `Biology Notes Bot`).
4. Придумайте username, обязательно заканчивающийся на `bot` (например `biology_notes_2025_bot`).
5. BotFather пришлёт **BOT_TOKEN** вида `123456789:AAH...`. Скопируйте.

> ⚠️ Никому не показывайте токен, не коммитьте `.env` в Git.

---

## 🆔 Шаг 2 — Узнаём свой ADMIN_ID

1. В Telegram откройте [@userinfobot](https://t.me/userinfobot) и нажмите `/start`.
2. Он пришлёт ваш числовой `id` — это и есть `ADMIN_ID`.

---

## 💻 Шаг 3 — Локальный запуск (для проверки)

```bash
git clone https://github.com/<ВАШ_АККАУНТ>/telegram-notes-bot.git
cd telegram-notes-bot

python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env                # Windows: copy .env.example .env
# Открыть .env и вписать BOT_TOKEN и ADMIN_ID

python main.py
```

Если в консоли появилось `Бот запущен: @имя_бота` — всё работает.
Откройте бота в Telegram и напишите `/start`.

---

## 📤 Шаг 4 — Загружаем GitHub

```bash
git init
git add .
git commit -m "init telegram notes bot"
git branch -M main
git remote add origin https://github.com/<ВАШ_АККАУНТ>/telegram-notes-bot.git
git push -u origin main
```

> Файл `.env` не попадёт в репозиторий — он в `.gitignore`.

---

## ☁️ Шаг 5а — Деплой на **Railway**

1. Зайдите на [railway.app](https://railway.app), войдите через GitHub.
2. **New Project → Deploy from GitHub repo** → выберите `telegram-notes-bot`.
3. Откройте проект → вкладка **Variables** → добавьте:
   - `BOT_TOKEN` = ваш токен
   - `ADMIN_ID` = ваш telegram id
4. Railway сам обнаружит `Procfile` и запустит `worker: python main.py`.
5. Во вкладке **Deployments → Logs** убедитесь, что есть строка `Бот запущен`.

> ⚠️ На бесплатном плане Railway файлы в `files/` и `bot.db` **могут пропадать после редеплоя**.
> Для надёжности подключите **Volume** (Settings → Volumes → Mount path: `/app`)
> или используйте платный план.

---

## ☁️ Шаг 5б — Деплой на **Replit**

1. Зайдите на [replit.com](https://replit.com), **Create Repl → Import from GitHub**.
2. Вставьте ссылку на репозиторий.
3. В меню слева откройте **Secrets** (иконка замка):
   - `BOT_TOKEN` = ваш токен
   - `ADMIN_ID` = ваш id
4. Нажмите **Run**.
5. Чтобы бот не засыпал — на бесплатном плане Replit веб-сервисы засыпают через ~5 минут;
   для постоянного бота используйте **Always On** (платная функция) либо Railway.

---

## 📥 Шаг 6 — Загружаем первые конспекты

1. Откройте бота в Telegram (вы как админ).
2. Напишите `/start` — увидите приветствие администратора.
3. Добавьте себя как ученика (для теста):
   `/add_student <ваш_id>`
4. Прикрепите PDF-файл и отправьте боту.
5. Бот спросит **номер** — напишите, например `1`.
6. Бот спросит **тему** — напишите, например `Клеточная мембрана`.
7. Готово! Теперь напишите `1` — и бот вернёт ваш PDF.

Чтобы добавить учеников:
- `/add_student 123456789`
- `/add_students @petya @vasya 987654321`

---

## ❓ Частые вопросы

**Бот не отвечает.**
Проверьте логи: правильный ли `BOT_TOKEN`, нет ли двух запущенных копий (Telegram разрешает только одну).

**Ученик добавлен по `@username`, но бот говорит «нет доступа».**
Telegram передаёт username не всегда. Лучше добавлять по числовому `telegram_id` —
ученик может узнать его у [@userinfobot](https://t.me/userinfobot).

**PDF пропал после редеплоя на Railway.**
Подключите Volume или храните файлы во внешнем хранилище (S3 / Telegram file_id — последний и так используется как кэш).

---

## 📝 Лицензия

MIT — используйте свободно.
