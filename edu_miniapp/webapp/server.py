"""Фабрика aiohttp-приложения: раздаёт фронтенд и монтирует API."""
from aiohttp import web

import config
from webapp import api

FRONTEND_DIR = config.BASE_DIR / "frontend"


async def index(request: web.Request) -> web.Response:
    return web.FileResponse(FRONTEND_DIR / "index.html")


def create_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot  # доступ к боту из API (отправка файлов/уведомлений)

    app.router.add_get("/", index)
    api.setup_routes(app)

    # Статика фронтенда (app.js, styles.css, ...)
    app.router.add_static("/static/", path=FRONTEND_DIR, name="static")
    return app
