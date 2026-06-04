"""Управляющие команды: бэкап БД и статистика.

  python manage.py backup
  python manage.py stats
"""
import shutil
import sqlite3
import sys
from datetime import datetime

import config

DB_FILE = config.BASE_DIR / config.DB_PATH


def backup() -> None:
    if not DB_FILE.exists():
        print("БД ещё не создана.")
        return
    backups = config.BASE_DIR / "backups"
    backups.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = backups / f"bot_{stamp}.db"
    shutil.copy2(DB_FILE, dst)
    print(f"Бэкап сохранён: {dst}")


def stats() -> None:
    if not DB_FILE.exists():
        print("БД ещё не создана.")
        return
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    def count(sql: str) -> int:
        try:
            return cur.execute(sql).fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    total = count("SELECT COUNT(*) FROM users")
    with_access = count("SELECT COUNT(*) FROM users WHERE has_access=1")
    curators = count("SELECT COUNT(*) FROM users WHERE role='curator'")
    admins = count("SELECT COUNT(*) FROM users WHERE role='admin'")
    groups = count("SELECT COUNT(*) FROM groups")
    worksheets = count("SELECT COUNT(*) FROM worksheets")
    checklists = count("SELECT COUNT(*) FROM checklists")
    subs = count("SELECT COUNT(*) FROM submissions")
    pract = count("SELECT COUNT(*) FROM practices")
    bookings = count("SELECT COUNT(*) FROM exam_bookings")

    print("=== Статистика ===")
    print(f"Пользователей всего : {total}")
    print(f"  с доступом        : {with_access}")
    print(f"  кураторов         : {curators}")
    print(f"  админов           : {admins}")
    print(f"Групп               : {groups}")
    print(f"Рабочих тетрадей    : {worksheets}")
    print(f"Чек-листов          : {checklists}")
    print(f"Сдач РТ             : {subs}")
    print(f"Практик             : {pract}")
    print(f"Записей на зачёт     : {bookings}")
    conn.close()


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("backup", "stats"):
        print(__doc__)
        return
    {"backup": backup, "stats": stats}[sys.argv[1]]()


if __name__ == "__main__":
    main()
