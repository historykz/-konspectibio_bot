"""Электронный журнал: предметы, уроки, оценки, рейтинг в группе.

Ключевой принцип безопасности: оценки всегда привязаны к telegram_id
(grades.student_id). Сервер отдаёт ученику только строки с его ID,
проверенным через подпись Telegram — поэтому чужие оценки увидеть нельзя.
"""
from typing import Any

from database.db import connect


async def journal_owner(journal_id: int) -> dict[str, Any] | None:
    """Вернуть {curator_id, group_id} журнала или None."""
    conn = await connect()
    async with conn.execute(
        """
        SELECT g.curator_id, g.id AS group_id
        FROM journals j JOIN groups g ON g.id = j.group_id
        WHERE j.id = ?
        """,
        (journal_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def lesson_owner(lesson_id: int) -> dict[str, Any] | None:
    """Вернуть {curator_id, group_id} по уроку или None."""
    conn = await connect()
    async with conn.execute(
        """
        SELECT g.curator_id, g.id AS group_id
        FROM lessons l
        JOIN journals j ON j.id = l.journal_id
        JOIN groups   g ON g.id = j.group_id
        WHERE l.id = ?
        """,
        (lesson_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


# ---------- Предметы (журналы) ----------

async def create_journal(group_id: int, title: str) -> int:
    conn = await connect()
    cur = await conn.execute(
        "INSERT INTO journals (group_id, title) VALUES (?, ?)", (group_id, title)
    )
    await conn.commit()
    return cur.lastrowid


async def list_journals(group_id: int) -> list[dict[str, Any]]:
    conn = await connect()
    async with conn.execute(
        "SELECT id, title FROM journals WHERE group_id = ? ORDER BY id", (group_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def journals_for_curator(curator_id: int) -> list[dict[str, Any]]:
    """Все журналы по всем группам куратора (для импорта/редактирования)."""
    conn = await connect()
    async with conn.execute(
        """
        SELECT j.id, j.title, g.id AS group_id, g.name AS group_name
        FROM journals j
        JOIN groups g ON g.id = j.group_id
        WHERE g.curator_id = ?
        ORDER BY g.name, j.title
        """,
        (curator_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ---------- Уроки (столбцы) ----------

async def add_lesson(
    journal_id: int, topic: str, max_score: float, lesson_date: str | None = None
) -> int:
    """Добавить столбец-урок в конец журнала."""
    conn = await connect()
    async with conn.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 AS pos FROM lessons WHERE journal_id = ?",
        (journal_id,),
    ) as cur:
        pos = (await cur.fetchone())["pos"]
    cur = await conn.execute(
        "INSERT INTO lessons (journal_id, position, topic, max_score, lesson_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (journal_id, pos, topic, max_score, lesson_date),
    )
    await conn.commit()
    return cur.lastrowid


async def set_grade(lesson_id: int, student_id: int, score: float | None) -> None:
    """Выставить/обновить балл ученику за урок."""
    conn = await connect()
    await conn.execute(
        """
        INSERT INTO grades (lesson_id, student_id, score)
        VALUES (?, ?, ?)
        ON CONFLICT(lesson_id, student_id) DO UPDATE SET score = excluded.score
        """,
        (lesson_id, student_id, score),
    )
    await conn.commit()


# ---------- Порядок учеников ----------

async def reorder_students(group_id: int, ordered_student_ids: list[int]) -> None:
    """Задать новый порядок учеников в группе (список ID по порядку)."""
    conn = await connect()
    for pos, sid in enumerate(ordered_student_ids, start=1):
        await conn.execute(
            "UPDATE group_students SET position = ? WHERE group_id = ? AND student_id = ?",
            (pos, group_id, sid),
        )
    await conn.commit()


# ---------- Рейтинг и сводка ----------

async def _journal_ranking(journal_id: int, group_id: int) -> list[dict[str, Any]]:
    """Сумма баллов каждого ученика группы по журналу, по убыванию."""
    conn = await connect()
    async with conn.execute(
        """
        SELECT gs.student_id,
               COALESCE(gs.full_name, u.first_name, '—') AS name,
               COALESCE(SUM(gr.score), 0)                AS total
        FROM group_students gs
        JOIN users u ON u.telegram_id = gs.student_id
        LEFT JOIN grades gr
               ON gr.student_id = gs.student_id
              AND gr.lesson_id IN (SELECT id FROM lessons WHERE journal_id = ?)
        WHERE gs.group_id = ?
        GROUP BY gs.student_id
        ORDER BY total DESC, name ASC
        """,
        (journal_id, group_id),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def _max_total(journal_id: int) -> float:
    conn = await connect()
    async with conn.execute(
        "SELECT COALESCE(SUM(max_score), 0) AS m FROM lessons WHERE journal_id = ?",
        (journal_id,),
    ) as cur:
        return (await cur.fetchone())["m"]


async def get_student_gradebook(student_id: int) -> list[dict[str, Any]]:
    """Полная сводка ученика по всем его журналам: уроки с баллами,
    итог, максимум и место в группе.

    Возвращает список журналов вида:
      {journal, group, lessons:[{topic, max_score, score, date}],
       total, max_total, rank, group_size}
    """
    conn = await connect()

    # Журналы групп, где состоит ученик
    async with conn.execute(
        """
        SELECT j.id AS journal_id, j.title, g.id AS group_id, g.name AS group_name
        FROM group_students gs
        JOIN groups   g ON g.id = gs.group_id
        JOIN journals j ON j.group_id = g.id
        WHERE gs.student_id = ?
        ORDER BY g.name, j.title
        """,
        (student_id,),
    ) as cur:
        journals = [dict(r) for r in await cur.fetchall()]

    result: list[dict[str, Any]] = []
    for j in journals:
        # Личные баллы по урокам
        async with conn.execute(
            """
            SELECT l.topic, l.max_score, l.lesson_date, gr.score
            FROM lessons l
            LEFT JOIN grades gr ON gr.lesson_id = l.id AND gr.student_id = ?
            WHERE l.journal_id = ?
            ORDER BY l.position
            """,
            (student_id, j["journal_id"]),
        ) as cur:
            lessons = [dict(r) for r in await cur.fetchall()]

        total = sum((l["score"] or 0) for l in lessons)
        max_total = await _max_total(j["journal_id"])

        ranking = await _journal_ranking(j["journal_id"], j["group_id"])
        group_size = len(ranking)
        rank = next(
            (i + 1 for i, r in enumerate(ranking) if r["student_id"] == student_id),
            None,
        )

        result.append({
            "journal": j["title"],
            "group": j["group_name"],
            "lessons": lessons,
            "total": round(total, 2),
            "max_total": round(max_total, 2),
            "rank": rank,
            "group_size": group_size,
            "percent": round(total / max_total * 100) if max_total else 0,
        })
    return result


async def get_journal_grid(journal_id: int, group_id: int) -> dict[str, Any]:
    """Полная таблица журнала для куратора: уроки (столбцы) × ученики (строки)."""
    conn = await connect()
    async with conn.execute(
        "SELECT id, position, topic, max_score, lesson_date FROM lessons "
        "WHERE journal_id = ? ORDER BY position",
        (journal_id,),
    ) as cur:
        lessons = [dict(r) for r in await cur.fetchall()]

    async with conn.execute(
        """
        SELECT gs.student_id,
               COALESCE(gs.full_name, u.first_name, '—') AS name,
               gs.position
        FROM group_students gs
        JOIN users u ON u.telegram_id = gs.student_id
        WHERE gs.group_id = ?
        ORDER BY gs.position, name
        """,
        (group_id,),
    ) as cur:
        students = [dict(r) for r in await cur.fetchall()]

    lesson_ids = [l["id"] for l in lessons]
    grades: dict[tuple[int, int], float] = {}
    if lesson_ids:
        ph = ",".join("?" * len(lesson_ids))
        async with conn.execute(
            f"SELECT lesson_id, student_id, score FROM grades WHERE lesson_id IN ({ph})",
            lesson_ids,
        ) as cur:
            async for r in cur:
                grades[(r["lesson_id"], r["student_id"])] = r["score"]

    rows = []
    for st in students:
        cells = [grades.get((l["id"], st["student_id"])) for l in lessons]
        total = sum((c or 0) for c in cells)
        rows.append({
            "student_id": st["student_id"],
            "name": st["name"],
            "cells": cells,
            "total": round(total, 2),
        })
    return {"lessons": lessons, "rows": rows}
