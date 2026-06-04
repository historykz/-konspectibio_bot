"""Слой доступа к данным. Здесь — каркас: пользователи, роли, доступы,
материалы и профиль. Остальные сущности добавляются по мере роста проекта."""
from typing import Any

import config
from database.db import connect

ROLES = ("user", "student", "curator", "admin")


# ---------- Пользователи и роли ----------

async def upsert_user(telegram_id: int, username: str | None, first_name: str | None) -> None:
    """Создать пользователя или обновить его username/имя (роль не трогаем)."""
    conn = await connect()
    await conn.execute(
        """
        INSERT INTO users (telegram_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username   = excluded.username,
            first_name = excluded.first_name
        """,
        (telegram_id, username, first_name),
    )
    await conn.commit()


async def get_user(telegram_id: int) -> dict[str, Any] | None:
    conn = await connect()
    async with conn.execute(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_role(telegram_id: int, role: str) -> None:
    if role not in ROLES:
        raise ValueError(f"Неизвестная роль: {role}")
    conn = await connect()
    await conn.execute(
        "UPDATE users SET role = ? WHERE telegram_id = ?", (role, telegram_id)
    )
    await conn.commit()


async def set_access(telegram_id: int, has_access: bool) -> None:
    conn = await connect()
    await conn.execute(
        "UPDATE users SET has_access = ? WHERE telegram_id = ?",
        (1 if has_access else 0, telegram_id),
    )
    await conn.commit()


async def find_by_username(username: str) -> dict[str, Any] | None:
    """Поиск по @username (без @). Работает только если человек уже писал боту."""
    uname = username.lstrip("@")
    conn = await connect()
    async with conn.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (uname,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def ensure_admins(admin_ids: list[int]) -> None:
    """При старте назначить указанных пользователей админами (и дать доступ)."""
    conn = await connect()
    for tid in admin_ids:
        await conn.execute(
            """
            INSERT INTO users (telegram_id, role, has_access)
            VALUES (?, 'admin', 1)
            ON CONFLICT(telegram_id) DO UPDATE SET role = 'admin', has_access = 1
            """,
            (tid,),
        )
    await conn.commit()


# ---------- Профиль ----------

async def get_profile(telegram_id: int) -> dict[str, Any] | None:
    """Профиль: роль, доступ, группа и куратор (если ученик)."""
    user = await get_user(telegram_id)
    if not user:
        return None
    conn = await connect()
    group_name = None
    curator_name = None
    async with conn.execute(
        """
        SELECT g.name AS group_name,
               cu.first_name AS curator_name,
               cu.username   AS curator_username
        FROM group_students gs
        JOIN groups g  ON g.id = gs.group_id
        JOIN users  cu ON cu.telegram_id = g.curator_id
        WHERE gs.student_id = ?
        LIMIT 1
        """,
        (telegram_id,),
    ) as cur:
        row = await cur.fetchone()
        if row:
            group_name = row["group_name"]
            curator_name = row["curator_name"] or (
                f"@{row['curator_username']}" if row["curator_username"] else None
            )
    return {
        "telegram_id": user["telegram_id"],
        "first_name": user["first_name"],
        "username": user["username"],
        "role": user["role"],
        "has_access": bool(user["has_access"]),
        "group_name": group_name,
        "curator_name": curator_name,
    }


# ---------- Материалы (рабочие тетради / чек-листы) ----------

async def list_worksheets() -> list[dict[str, Any]]:
    conn = await connect()
    async with conn.execute(
        "SELECT id, title, file_type FROM worksheets ORDER BY id"
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_worksheet(ws_id: int) -> dict[str, Any] | None:
    conn = await connect()
    async with conn.execute(
        "SELECT * FROM worksheets WHERE id = ?", (ws_id,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_worksheet(title: str, file_id: str, file_type: str) -> int:
    conn = await connect()
    cur = await conn.execute(
        "INSERT INTO worksheets (title, file_id, file_type) VALUES (?, ?, ?)",
        (title, file_id, file_type),
    )
    await conn.commit()
    return cur.lastrowid


async def list_checklists() -> list[dict[str, Any]]:
    conn = await connect()
    async with conn.execute(
        "SELECT id, title, file_type FROM checklists ORDER BY id"
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ---------- Группы и ученики (для куратора) ----------

async def create_group(name: str, curator_id: int) -> int:
    conn = await connect()
    cur = await conn.execute(
        "INSERT INTO groups (name, curator_id) VALUES (?, ?)", (name, curator_id)
    )
    await conn.commit()
    return cur.lastrowid


async def curator_owns_group(curator_id: int, group_id: int) -> bool:
    conn = await connect()
    async with conn.execute(
        "SELECT 1 FROM groups WHERE id = ? AND curator_id = ?", (group_id, curator_id)
    ) as cur:
        return await cur.fetchone() is not None


async def list_groups_for_curator(curator_id: int) -> list[dict[str, Any]]:
    conn = await connect()
    async with conn.execute(
        """
        SELECT g.id, g.name,
               (SELECT COUNT(*) FROM group_students gs WHERE gs.group_id = g.id) AS students
        FROM groups g
        WHERE g.curator_id = ?
        ORDER BY g.name
        """,
        (curator_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def list_group_students(group_id: int) -> list[dict[str, Any]]:
    conn = await connect()
    async with conn.execute(
        """
        SELECT gs.student_id, gs.position,
               COALESCE(gs.full_name, u.first_name, '—') AS name,
               u.username
        FROM group_students gs
        JOIN users u ON u.telegram_id = gs.student_id
        WHERE gs.group_id = ?
        ORDER BY gs.position, name
        """,
        (group_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def add_student_to_group(
    group_id: int, student_id: int, full_name: str | None = None
) -> None:
    """Добавить ученика в группу (в конец списка), выдать роль и доступ."""
    conn = await connect()
    # Пользователь должен существовать; повышаем до student (не трогая curator/admin)
    await conn.execute(
        """
        INSERT INTO users (telegram_id, role, has_access) VALUES (?, 'student', 1)
        ON CONFLICT(telegram_id) DO UPDATE SET
            has_access = 1,
            role = CASE WHEN users.role = 'user' THEN 'student' ELSE users.role END
        """,
        (student_id,),
    )
    async with conn.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 AS pos FROM group_students WHERE group_id = ?",
        (group_id,),
    ) as cur:
        pos = (await cur.fetchone())["pos"]
    await conn.execute(
        "INSERT INTO group_students (group_id, student_id, full_name, position) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(group_id, student_id) DO UPDATE SET full_name = COALESCE(excluded.full_name, full_name)",
        (group_id, student_id, full_name, pos),
    )
    await conn.commit()


async def set_student_full_name(group_id: int, student_id: int, full_name: str) -> None:
    conn = await connect()
    await conn.execute(
        "UPDATE group_students SET full_name = ? WHERE group_id = ? AND student_id = ?",
        (full_name, group_id, student_id),
    )
    await conn.commit()


async def remove_student_from_group(group_id: int, student_id: int) -> None:
    conn = await connect()
    await conn.execute(
        "DELETE FROM group_students WHERE group_id = ? AND student_id = ?",
        (group_id, student_id),
    )
    await conn.commit()
