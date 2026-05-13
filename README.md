# 📘 Telegram-бот для выдачи PDF-конспектов

Бот выдаёт ученикам PDF-конспекты по номеру. Только разрешённые ученики могут получать файлы. Админ загружает PDF через бота, управляет учениками и конспектами.

## Стек
- Python 3.11
- aiogram 3
- SQLite (через aiosqlite)
- Railway / Replit / локальный запуск

---

## 1. Структура проекта

```
bot/
├── main.py              # точка входа
├── config.py            # конфиг + .env
├── database.py          # работа с SQLite
├── keyboards.py         # инлайн-клавиатуры
├── utils.py             # вспомогательные функции
├── handlers/
│   ├── admin.py         # команды админа + загрузка PDF
│   └── user.py          # команды учеников
├── files/               # сюда сохраняются PDF
├── requirements.txt
├── Procfile             # для Railway
├── runtime.txt          # версия Python
├── .env.example
└── .gitignore
```

---

## 2. Создание Telegram-бота через BotFather

1. В Telegram найди **@BotFather**.
2. Отправь `/newbot`.
3. Придумай имя (например, `Конспекты по биологии`) и username (должен заканчиваться на `bot`, например `bio_notes_bot`).
4. BotFather пришлёт **токен** — длинную строку вида `123456789:AAH...`. Скопируй его.

---

## 3. Получение ADMIN_ID

1. В Telegram найди бота **@userinfobot**.
2. Отправь ему любое сообщение.
3. Он пришлёт твой числовой ID — это и есть `ADMIN_ID`.

---

## 4. Запуск локально (для проверки)

```bash
git clone <твой репозиторий>
cd bot
python -m venv venv
source venv/bin/activate        # на Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# открой .env и впиши свои BOT_TOKEN и ADMIN_ID
python main.py
```

Если в консоли появилось `Бот запускается...` — всё работает. Открой бота в Telegram и отправь `/start`.

---

## 5. Деплой на Railway

1. Зарегистрируйся на [railway.app](https://railway.app) через GitHub.
2. Залей проект на GitHub:
   ```bash
   git init
   git add .
   git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/USERNAME/REPO.git
   git push -u origin main
   ```
3. В Railway: **New Project → Deploy from GitHub repo** → выбери репозиторий.
4. После создания проекта зайди в **Variables** и добавь:
   - `BOT_TOKEN` — токен от BotFather
   - `ADMIN_ID` — твой числовой ID
5. Railway автоматически прочитает `Procfile` и запустит `python main.py`.
6. Если процесс не стартовал сам — зайди в **Settings → Deploy** и проверь, что start command пустой (Railway возьмёт его из Procfile) либо явно укажи `python main.py`.
7. Логи смотри во вкладке **Deployments → View Logs**.

### ⚠️ Важно про файлы на Railway
Файловая система на Railway **эфемерная** — при редеплое папка `files/` обнуляется.
Бот хранит `file_id` каждого PDF в Telegram, поэтому отправка ученикам продолжит работать даже если локальные файлы пропали (Telegram сам отдаст файл по своему ID). Но если ты хочешь полную надёжность — подключи в Railway **Volume** и смонтируй его в `/app/files`.

---

## 6. Первые шаги после запуска

1. В Telegram открой своего бота → `/start`. Должно появиться админское меню.
2. Добавь себя как ученика для теста: `/add_student <твой ID>`.
3. Отправь боту любой PDF-файл.
4. Бот спросит номер — введи, например, `1`.
5. Бот спросит тему — введи, например, `Клеточная мембрана`.
6. Готово. Теперь отправь боту просто `1` — он пришлёт PDF.

---

## 7. Команды

### Ученик
| Команда | Что делает |
|---|---|
| `/start` | Приветствие |
| `<число>` | Получить PDF по номеру |
| `/list` | Список доступных конспектов |

### Админ
| Команда | Что делает |
|---|---|
| `/add_student <id\|@username>` | Добавить ученика |
| `/add_students @u1 @u2 123` | Массовое добавление |
| `/remove_student <id\|@username>` | Удалить ученика |
| `/students` | Список учеников |
| `/notes` | Список конспектов |
| `/delete_note <номер>` | Удалить конспект |
| отправить PDF | Загрузить новый конспект (бот спросит номер и тему) |

---

## 8. Если что-то не работает

- **Бот не отвечает** → проверь логи Railway. Скорее всего неверный `BOT_TOKEN` или забыл переменные окружения.
- **«У вас нет доступа»** в роли админа → значит `ADMIN_ID` в `.env` не совпадает с твоим реальным ID.
- **PDF не сохраняется** → убедись что есть права на запись в папку `files/`. На Railway проверь volume.
- **`/add_student @username` не работает с конкретным юзером** → Telegram не даёт получить ID по @username, пока пользователь сам не напишет боту. Лучше всегда добавлять по числовому ID.
