"""Применение разобранной таблицы к журналу: сопоставление ФИО → ученики,
создание уроков и выставление баллов. Несопоставленные ФИО возвращаются."""
from typing import Any

from database.db import connect
from database import gradebook
from services.import_sheet import _norm


async def _roster(group_id: int) -> dict[str, int]:
    """{нормализованное_ФИО: student_id} по ученикам группы.
    Сопоставляем и по full_name, и по имени из Telegram."""
    conn = await connect()
    mapping: dict[str, int] = {}
    async with conn.execute(
        """
        SELECT gs.student_id, gs.full_name, u.first_name
        FROM group_students gs
        JOIN users u ON u.telegram_id = gs.student_id
        WHERE gs.group_id = ?
        """,
        (group_id,),
    ) as cur:
        async for r in cur:
            for cand in (r["full_name"], r["first_name"]):
                if cand and str(cand).strip():
                    mapping[_norm(str(cand))] = r["student_id"]
    return mapping


async def apply_import(
    journal_id: int, group_id: int, parsed: dict[str, Any], replace: bool = True
) -> dict[str, Any]:
    """Залить данные в журнал.

    replace=True — журнал пересобирается: старые уроки и баллы удаляются,
    создаются заново из таблицы (удобно для повторной синхронизации).

    Возвращает отчёт: сколько уроков, сопоставленных/несопоставленных учеников.
    """
    conn = await connect()

    if replace:
        await conn.execute("DELETE FROM lessons WHERE journal_id = ?", (journal_id,))
        await conn.commit()

    # Создаём уроки (столбцы)
    lesson_ids: list[int] = []
    for lesson in parsed["lessons"]:
        lid = await gradebook.add_lesson(
            journal_id, lesson["topic"], float(lesson["max_score"])
        )
        lesson_ids.append(lid)

    roster = await _roster(group_id)
    matched: list[str] = []
    unmatched: list[str] = []

    for st in parsed["students"]:
        sid = roster.get(_norm(st["name"]))
        if sid is None:
            unmatched.append(st["name"])
            continue
        matched.append(st["name"])
        for lid, score in zip(lesson_ids, st["scores"]):
            if score is not None:
                await gradebook.set_grade(lid, sid, score)

    await conn.commit()
    return {
        "lessons": len(lesson_ids),
        "matched": matched,
        "unmatched": unmatched,
    }
