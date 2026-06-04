"""Импорт журнала через бота.

Куратор отправляет боту файл (.xlsx/.csv, выгруженный из Google Sheets).
Бот разбирает его, показывает список журналов куратора кнопками,
после выбора заливает данные и присылает отчёт о сопоставлении ФИО.
"""
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from database import gradebook, repo
from services import roles
from services.import_apply import apply_import
from services.import_sheet import parse_sheet

log = logging.getLogger(__name__)
router = Router()

# Временное хранилище разобранных таблиц: {curator_id: parsed}
_pending: dict[int, dict] = {}

ALLOWED_EXT = (".xlsx", ".xlsm", ".csv", ".tsv")


@router.message(F.document)
async def on_document(message: Message, bot: Bot) -> None:
    profile = await repo.get_profile(message.from_user.id)
    if not profile or not roles.is_curator(profile["role"]):
        return  # не куратор — игнорируем (документ может быть РТ и т.п.)

    doc = message.document
    name = doc.file_name or ""
    if not name.lower().endswith(ALLOWED_EXT):
        return  # не таблица — пропускаем

    dest = config.TEMP_DIR / f"import_{message.from_user.id}_{name}"
    await bot.download(doc, destination=dest)

    try:
        parsed = parse_sheet(str(dest))
    except Exception as e:  # noqa: BLE001 - показываем причину куратору
        await message.answer(f"❌ Не удалось разобрать таблицу:\n{e}")
        Path(dest).unlink(missing_ok=True)
        return
    finally:
        Path(dest).unlink(missing_ok=True)

    if not parsed["students"]:
        await message.answer("В таблице не найдено ни одного ученика.")
        return

    _pending[message.from_user.id] = parsed

    journals = await gradebook.journals_for_curator(message.from_user.id)
    if not journals:
        await message.answer(
            "Таблица распознана, но у вас ещё нет журналов. "
            "Создайте журнал в приложении (раздел «Журнал оценок»), затем пришлите файл снова."
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{j['group_name']} · {j['title']}",
            callback_data=f"imp:{j['id']}:{j['group_id']}",
        )]
        for j in journals
    ])
    await message.answer(
        f"📥 Распознано: уроков — {len(parsed['lessons'])}, "
        f"учеников — {len(parsed['students'])}.\n"
        f"В какой журнал импортировать?",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("imp:"))
async def on_pick_journal(cb: CallbackQuery) -> None:
    parsed = _pending.get(cb.from_user.id)
    if not parsed:
        await cb.answer("Данные устарели, пришлите файл заново.", show_alert=True)
        return

    _, jid, gid = cb.data.split(":")
    report = await apply_import(int(jid), int(gid), parsed)
    _pending.pop(cb.from_user.id, None)

    text = (
        f"✅ Импорт завершён.\n"
        f"Уроков создано: {report['lessons']}\n"
        f"Учеников обновлено: {len(report['matched'])}"
    )
    if report["unmatched"]:
        names = ", ".join(report["unmatched"])
        text += (
            f"\n\n⚠️ Не нашлись в группе ({len(report['unmatched'])}): {names}\n"
            f"Проверьте, что эти ученики добавлены в группу и их ФИО совпадает."
        )
    await cb.message.edit_text(text)
    await cb.answer()
