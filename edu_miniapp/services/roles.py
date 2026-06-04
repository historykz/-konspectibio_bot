"""Логика ролей: иерархия доступа и построение меню для фронтенда."""

# Иерархия: каждая следующая роль включает возможности предыдущей.
_LEVEL = {"user": 0, "student": 1, "curator": 2, "admin": 3}


def has_at_least(role: str, required: str) -> bool:
    return _LEVEL.get(role, 0) >= _LEVEL.get(required, 99)


def is_student(role: str) -> bool:
    return has_at_least(role, "student")


def is_curator(role: str) -> bool:
    return has_at_least(role, "curator")


def is_admin(role: str) -> bool:
    return role == "admin"


def build_menu(role: str, has_access: bool) -> list[dict]:
    """Список пунктов меню для текущей роли. Фронтенд рендерит их кнопками.

    Каждый пункт: {key, title, icon, group}.
    key используется фронтендом для перехода к экрану / вызова API.
    """
    menu: list[dict] = []

    # Раздел ученика — доступен student/curator/admin при наличии доступа
    if is_student(role) and has_access:
        menu += [
            {"key": "worksheets",   "title": "Рабочие тетради",  "icon": "📚", "group": "Обучение"},
            {"key": "submit_rt",    "title": "Сдать тетрадь",    "icon": "📤", "group": "Обучение"},
            {"key": "submit_pr",    "title": "Скрин практики",   "icon": "📸", "group": "Обучение"},
            {"key": "checklists",   "title": "Чек-листы",        "icon": "✅", "group": "Обучение"},
            {"key": "exam_book",    "title": "Запись на зачёт",  "icon": "🗓", "group": "Обучение"},
            {"key": "my_grades",    "title": "Мои баллы",        "icon": "🏆", "group": "Обучение"},
            {"key": "my_subs",      "title": "Мои сдачи",        "icon": "📋", "group": "История"},
            {"key": "my_pract",     "title": "Мои практики",     "icon": "📸", "group": "История"},
            {"key": "profile",      "title": "Мой профиль",      "icon": "👤", "group": "История"},
        ]

    # Раздел куратора
    if is_curator(role):
        menu += [
            {"key": "my_groups",    "title": "Мои группы",        "icon": "👥", "group": "Куратор"},
            {"key": "my_students",  "title": "Мои ученики",       "icon": "👨‍🎓", "group": "Куратор"},
            {"key": "got_subs",     "title": "Сданные РТ",        "icon": "📥", "group": "Куратор"},
            {"key": "got_pract",    "title": "Практики учеников", "icon": "📸", "group": "Куратор"},
            {"key": "exam_create",  "title": "Расписание зачётов","icon": "🗓", "group": "Куратор"},
            {"key": "journal",      "title": "Журнал оценок",     "icon": "📒", "group": "Куратор"},
        ]

    # Раздел админа
    if is_admin(role):
        menu += [
            {"key": "adm_worksheets","title": "Управление РТ",      "icon": "📚", "group": "Админ"},
            {"key": "adm_checklists","title": "Управление чек-листами","icon": "✅", "group": "Админ"},
            {"key": "adm_access",    "title": "Управление доступом", "icon": "🔑", "group": "Админ"},
            {"key": "adm_curators",  "title": "Кураторы",            "icon": "👨‍🏫", "group": "Админ"},
            {"key": "adm_students",  "title": "Ученики",             "icon": "👨‍🎓", "group": "Админ"},
            {"key": "adm_groups",    "title": "Группы",              "icon": "👥", "group": "Админ"},
            {"key": "adm_export",    "title": "Экспорт в Excel",     "icon": "📊", "group": "Админ"},
        ]

    return menu
