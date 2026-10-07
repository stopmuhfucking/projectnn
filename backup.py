"""Резервное копирование и восстановление (полная копия средствами sqlite3)."""
import logging
import os
import sqlite3
from datetime import datetime

import db

BACKUP_DIR = os.path.join(db.BASE_DIR, "backups")


def check_file(path):
    """Проверка целостности файла БД."""
    conn = sqlite3.connect(path)
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    return result == "ok"


def make_backup():
    """Создаёт копию БД в папке backups. Возвращает путь к файлу."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = "bookstore_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
    path = os.path.join(BACKUP_DIR, name)
    source = db.connect()
    target = sqlite3.connect(path)
    source.backup(target)       # копирование работает, даже если БД сейчас используется
    target.close()
    source.close()
    if not check_file(path):
        os.remove(path)
        raise RuntimeError("Копия не прошла проверку целостности")
    logging.info("Создана резервная копия: %s", name)
    return path


def restore_backup(path):
    """Восстанавливает БД из файла копии (перед этим проверяет копию)."""
    if not check_file(path):
        raise RuntimeError("Файл копии повреждён")
    source = sqlite3.connect(path)
    target = sqlite3.connect(db.DB_PATH)
    source.backup(target)
    target.close()
    source.close()
    logging.info("БД восстановлена из копии: %s", os.path.basename(path))


if __name__ == "__main__":
    db.setup_logging()
    print("Копия создана:", make_backup())
