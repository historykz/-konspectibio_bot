"""API мини-приложения. Каждый запрос аутентифицируется через initData.

Фронтенд присылает initData в заголовке X-Init-Data.
"""
from functools import wraps

from aiohttp import web

from database import repo
from database import gradebook
from services import roles
from webapp.auth import validate_init_data


def authenticated(handler):
    """Декоратор: проверяет initData, кладёт user в request['tg_user']."""

    @wraps(handler)
    async def wrapper(request: web.Request):
        init_data = request.headers.get("X-Init-Data", "")
        tg_user = validate_init_data(init_data)
        if not tg_user or "id" not in tg_user:
            return web.json_response({"error": "unauthorized"}, status=401)
        request["tg_user"] = tg_user
        return await handler(request)

    return wrapper


def requires_access(handler):
    """Декоратор поверх authenticated: требует доступ к материалам."""

    @wraps(handler)
    async def wrapper(request: web.Request):
        profile = await repo.get_profile(request["tg_user"]["id"])
        if not profile or not (profile["has_access"] and roles.is_student(profile["role"])):
            return web.json_response({"error": "forbidden"}, status=403)
        request["profile"] = profile
        return await handler(request)

    return wrapper


# ---------- Эндпоинты ----------

@authenticated
async def me(request: web.Request) -> web.Response:
    """Регистрирует/обновляет пользователя и возвращает профиль + меню."""
    tg = request["tg_user"]
    await repo.upsert_user(
        telegram_id=tg["id"],
        username=tg.get("username"),
        first_name=tg.get("first_name"),
    )
    profile = await repo.get_profile(tg["id"])
    menu = roles.build_menu(profile["role"], profile["has_access"])
    return web.json_response({"profile": profile, "menu": menu})


@authenticated
@requires_access
async def worksheets(request: web.Request) -> web.Response:
    items = await repo.list_worksheets()
    return web.json_response({"items": items})


@authenticated
@requires_access
async def checklists(request: web.Request) -> web.Response:
    items = await repo.list_checklists()
    return web.json_response({"items": items})


@authenticated  # noqa
async def get_file(request: web.Request) -> web.Response:
    """Отправляет файл рабочей тетради в чат пользователю через бота.

    Файл уходит в Telegram-чат (а не скачивается в мини-приложении) —
    так работает кэш по file_id и привычная выдача материалов.
    """
    bot = request.app["bot"]
    ws_id = int(request.match_info["ws_id"])
    ws = await repo.get_worksheet(ws_id)
    if not ws:
        return web.json_response({"error": "not_found"}, status=404)

    profile = await repo.get_profile(request["tg_user"]["id"])
    if not profile or not (profile["has_access"] and roles.is_student(profile["role"])):
        return web.json_response({"error": "forbidden"}, status=403)

    chat_id = request["tg_user"]["id"]
    if ws["file_type"] == "photo":
        await bot.send_photo(chat_id, ws["file_id"], caption=ws["title"])
    else:
        await bot.send_document(chat_id, ws["file_id"], caption=ws["title"])
    return web.json_response({"ok": True})


@authenticated
@requires_access
async def my_grades(request: web.Request) -> web.Response:
    """Сводка ученика: оценки по урокам, итог, максимум, место в группе."""
    data = await gradebook.get_student_gradebook(request["tg_user"]["id"])
    return web.json_response({"journals": data})


@authenticated
async def curator_journals(request: web.Request) -> web.Response:
    """Список журналов куратора (по всем его группам)."""
    profile = await repo.get_profile(request["tg_user"]["id"])
    if not profile or not roles.is_curator(profile["role"]):
        return web.json_response({"error": "forbidden"}, status=403)
    items = await gradebook.journals_for_curator(request["tg_user"]["id"])
    return web.json_response({"items": items})


@authenticated
async def journal_grid(request: web.Request) -> web.Response:
    """Таблица одного журнала (ученики × уроки) для куратора."""
    profile = await repo.get_profile(request["tg_user"]["id"])
    if not profile or not roles.is_curator(profile["role"]):
        return web.json_response({"error": "forbidden"}, status=403)
    journal_id = int(request.match_info["journal_id"])
    group_id = int(request.query.get("group_id", "0"))
    grid = await gradebook.get_journal_grid(journal_id, group_id)
    return web.json_response(grid)


def curator_only(handler):
    """Декоратор поверх authenticated: требует роль куратора и кладёт profile."""

    @wraps(handler)
    async def wrapper(request: web.Request):
        profile = await repo.get_profile(request["tg_user"]["id"])
        if not profile or not roles.is_curator(profile["role"]):
            return web.json_response({"error": "forbidden"}, status=403)
        request["profile"] = profile
        return await handler(request)

    return wrapper


@authenticated
@curator_only
async def curator_groups(request: web.Request) -> web.Response:
    items = await repo.list_groups_for_curator(request["tg_user"]["id"])
    return web.json_response({"items": items})


@authenticated
@curator_only
async def create_group(request: web.Request) -> web.Response:
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "empty_name"}, status=400)
    gid = await repo.create_group(name, request["tg_user"]["id"])
    return web.json_response({"id": gid, "name": name})


async def _guard_group(request: web.Request) -> int | None:
    """Проверить, что текущий куратор владеет группой из URL. Вернуть group_id или None."""
    group_id = int(request.match_info["group_id"])
    if not await repo.curator_owns_group(request["tg_user"]["id"], group_id):
        return None
    return group_id


@authenticated
@curator_only
async def group_students(request: web.Request) -> web.Response:
    gid = await _guard_group(request)
    if gid is None:
        return web.json_response({"error": "forbidden"}, status=403)
    items = await repo.list_group_students(gid)
    journals = await gradebook.list_journals(gid)
    return web.json_response({"students": items, "journals": journals})


@authenticated
@curator_only
async def add_student(request: web.Request) -> web.Response:
    gid = await _guard_group(request)
    if gid is None:
        return web.json_response({"error": "forbidden"}, status=403)
    body = await request.json()
    identifier = str(body.get("identifier", "")).strip()
    full_name = (body.get("full_name") or "").strip() or None

    # Разрешаем по Telegram ID или @username (username — только если уже писал боту)
    if identifier.lstrip("-").isdigit():
        student_id = int(identifier)
    else:
        u = await repo.find_by_username(identifier)
        if not u:
            return web.json_response(
                {"error": "user_not_found",
                 "detail": "Этого @username нет в базе — он должен сначала написать боту /start"},
                status=404,
            )
        student_id = u["telegram_id"]

    await repo.add_student_to_group(gid, student_id, full_name)
    bot = request.app["bot"]
    try:
        await bot.send_message(student_id, "✅ Вас добавили в группу, доступ к материалам открыт.")
    except Exception:  # noqa: BLE001
        pass
    return web.json_response({"ok": True, "student_id": student_id})


@authenticated
@curator_only
async def rename_student(request: web.Request) -> web.Response:
    gid = await _guard_group(request)
    if gid is None:
        return web.json_response({"error": "forbidden"}, status=403)
    sid = int(request.match_info["sid"])
    body = await request.json()
    await repo.set_student_full_name(gid, sid, (body.get("full_name") or "").strip())
    return web.json_response({"ok": True})


@authenticated
@curator_only
async def remove_student(request: web.Request) -> web.Response:
    gid = await _guard_group(request)
    if gid is None:
        return web.json_response({"error": "forbidden"}, status=403)
    sid = int(request.match_info["sid"])
    await repo.remove_student_from_group(gid, sid)
    return web.json_response({"ok": True})


@authenticated
@curator_only
async def reorder_students(request: web.Request) -> web.Response:
    gid = await _guard_group(request)
    if gid is None:
        return web.json_response({"error": "forbidden"}, status=403)
    body = await request.json()
    order = [int(x) for x in body.get("order", [])]
    await gradebook.reorder_students(gid, order)
    return web.json_response({"ok": True})


@authenticated
@curator_only
async def create_journal(request: web.Request) -> web.Response:
    gid = await _guard_group(request)
    if gid is None:
        return web.json_response({"error": "forbidden"}, status=403)
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        return web.json_response({"error": "empty_title"}, status=400)
    jid = await gradebook.create_journal(gid, title)
    return web.json_response({"id": jid, "title": title})


@authenticated
@curator_only
async def add_lesson(request: web.Request) -> web.Response:
    journal_id = int(request.match_info["journal_id"])
    owner = await gradebook.journal_owner(journal_id)
    if not owner or owner["curator_id"] != request["tg_user"]["id"]:
        return web.json_response({"error": "forbidden"}, status=403)
    body = await request.json()
    topic = (body.get("topic") or "").strip()
    try:
        max_score = float(body.get("max_score"))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_max"}, status=400)
    if not topic:
        return web.json_response({"error": "empty_topic"}, status=400)
    lid = await gradebook.add_lesson(journal_id, topic, max_score)
    return web.json_response({"id": lid})


@authenticated
@curator_only
async def set_grade(request: web.Request) -> web.Response:
    body = await request.json()
    lesson_id = int(body.get("lesson_id"))
    student_id = int(body.get("student_id"))
    owner = await gradebook.lesson_owner(lesson_id)
    if not owner or owner["curator_id"] != request["tg_user"]["id"]:
        return web.json_response({"error": "forbidden"}, status=403)
    raw = body.get("score")
    score = None if raw in (None, "", "·") else float(raw)
    await gradebook.set_grade(lesson_id, student_id, score)
    return web.json_response({"ok": True})


def setup_routes(app: web.Application) -> None:
    app.router.add_post("/api/me", me)
    app.router.add_get("/api/worksheets", worksheets)
    app.router.add_get("/api/checklists", checklists)
    app.router.add_post("/api/worksheets/{ws_id}/send", get_file)
    app.router.add_get("/api/my-grades", my_grades)
    app.router.add_get("/api/curator/journals", curator_journals)
    app.router.add_get("/api/curator/journals/{journal_id}/grid", journal_grid)
    # управление группами/учениками
    app.router.add_get("/api/curator/groups", curator_groups)
    app.router.add_post("/api/curator/groups", create_group)
    app.router.add_get("/api/curator/groups/{group_id}/students", group_students)
    app.router.add_post("/api/curator/groups/{group_id}/students", add_student)
    app.router.add_patch("/api/curator/groups/{group_id}/students/{sid}", rename_student)
    app.router.add_delete("/api/curator/groups/{group_id}/students/{sid}", remove_student)
    app.router.add_post("/api/curator/groups/{group_id}/reorder", reorder_students)
    app.router.add_post("/api/curator/groups/{group_id}/journals", create_journal)
    # журнал
    app.router.add_post("/api/curator/journals/{journal_id}/lessons", add_lesson)
    app.router.add_post("/api/curator/grades", set_grade)
