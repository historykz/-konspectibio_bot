-- =========================================================
--  Схема БД образовательного Telegram Mini App
-- =========================================================

PRAGMA foreign_keys = ON;

-- Пользователи и роли. role: user | student | curator | admin
CREATE TABLE IF NOT EXISTS users (
    telegram_id   INTEGER PRIMARY KEY,
    username      TEXT,
    first_name    TEXT,
    role          TEXT    NOT NULL DEFAULT 'user',
    has_access    INTEGER NOT NULL DEFAULT 0,   -- доступ к материалам (0/1)
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Группы (создаёт куратор или админ)
CREATE TABLE IF NOT EXISTS groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    curator_id  INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Связь ученик <-> группа
CREATE TABLE IF NOT EXISTS group_students (
    group_id    INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    full_name   TEXT,                          -- ФИО ученика в журнале (для импорта/сортировки)
    position    INTEGER NOT NULL DEFAULT 0,     -- порядок ученика в группе (можно менять)
    PRIMARY KEY (group_id, student_id)
);

-- Рабочие тетради
CREATE TABLE IF NOT EXISTS worksheets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    file_id     TEXT    NOT NULL,   -- Telegram file_id для мгновенной отправки
    file_type   TEXT    NOT NULL,   -- document/photo/...
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Чек-листы
CREATE TABLE IF NOT EXISTS checklists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    file_id     TEXT    NOT NULL,
    file_type   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Сдачи рабочих тетрадей (готовый PDF)
CREATE TABLE IF NOT EXISTS submissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    full_name   TEXT    NOT NULL,
    group_id    INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    pdf_path    TEXT,
    file_id     TEXT,               -- кэш отправленного PDF
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Практики (скрины) — отдельный раздел с темой
CREATE TABLE IF NOT EXISTS practices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    full_name   TEXT    NOT NULL,
    topic       TEXT    NOT NULL,
    group_id    INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    pdf_path    TEXT,
    file_id     TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Буфер фото на время сдачи (временно, до сборки PDF)
CREATE TABLE IF NOT EXISTS photo_buffer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL,
    kind        TEXT    NOT NULL,   -- submission | practice
    file_id     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Слоты зачётов
CREATE TABLE IF NOT EXISTS exam_slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    curator_id  INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    slot_dt     TEXT    NOT NULL,   -- ISO datetime начала слота
    meet_link   TEXT    NOT NULL,
    is_booked   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Записи на зачёт
CREATE TABLE IF NOT EXISTS exam_bookings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id           INTEGER NOT NULL REFERENCES exam_slots(id) ON DELETE CASCADE,
    student_id        INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    full_name         TEXT    NOT NULL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    reminded_10       INTEGER NOT NULL DEFAULT 0,  -- флаг "напомнили за 10 мин"
    started_notified  INTEGER NOT NULL DEFAULT 0   -- флаг "уведомили о начале"
);

-- =========================================================
--  ЭЛЕКТРОННЫЙ ЖУРНАЛ (оценки, как в Платонусе)
-- =========================================================

-- Предмет/журнал внутри группы (на группу можно несколько предметов)
CREATE TABLE IF NOT EXISTS journals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id    INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,              -- напр. "Биология"
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Уроки = столбцы журнала
CREATE TABLE IF NOT EXISTS lessons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_id  INTEGER NOT NULL REFERENCES journals(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,              -- порядок столбца
    topic       TEXT    NOT NULL,              -- тема урока
    max_score   REAL    NOT NULL,              -- максимальный балл
    lesson_date TEXT,                          -- дата урока (необязательно)
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Оценки = ячейки журнала. score = NULL означает "ещё не оценён / н/б"
CREATE TABLE IF NOT EXISTS grades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id   INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    score       REAL,
    UNIQUE (lesson_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_journals_group  ON journals(group_id);
CREATE INDEX IF NOT EXISTS idx_lessons_journal ON lessons(journal_id);
CREATE INDEX IF NOT EXISTS idx_grades_student  ON grades(student_id);
CREATE INDEX IF NOT EXISTS idx_grades_lesson   ON grades(lesson_id);

CREATE INDEX IF NOT EXISTS idx_groups_curator   ON groups(curator_id);
CREATE INDEX IF NOT EXISTS idx_subs_student      ON submissions(student_id);
CREATE INDEX IF NOT EXISTS idx_pract_student     ON practices(student_id);
CREATE INDEX IF NOT EXISTS idx_slots_curator     ON exam_slots(curator_id);
CREATE INDEX IF NOT EXISTS idx_bookings_student  ON exam_bookings(student_id);
