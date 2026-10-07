"""Подключение к SQLite, создание базы и настройка логирования."""
import logging
import os
import sqlite3

from auth import hash_password

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bookstore.db")
LOG_PATH = os.path.join(BASE_DIR, "app.log")


def setup_logging():
    """Все события программы пишутся в файл app.log."""
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
    )


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row            # доступ к столбцам по имени
    conn.execute("PRAGMA foreign_keys = ON")  # в SQLite внешние ключи включаются вручную
    # LIKE в SQLite не понимает регистр русских букв, поэтому добавляем свою функцию
    conn.create_function("lower_ru", 1, lambda s: s.lower() if s else s)
    return conn


def run_script(conn, file_name):
    path = os.path.join(BASE_DIR, "sql", file_name)
    with open(path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())


def init_db():
    """Создаёт БД с нуля: таблицы, представления, триггеры, тестовые данные, пароли."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = connect()
    run_script(conn, "bookstore.sql")

    # Сотрудники (пароли только в виде хеша)
    conn.executemany(
        "INSERT INTO Employees (full_name, role, login, password_hash) VALUES (?, ?, ?, ?)",
        [("Владелец магазина", "owner",   "owner",   hash_password("owner123")),
         ("Менеджер Пётр",     "manager", "manager", hash_password("manager123"))])
    conn.commit()

    run_script(conn, "seed.sql")

    # Логины читателей (клиентов)
    conn.execute("UPDATE Customers SET login = 'reader', password_hash = ? WHERE id = 1",
                 (hash_password("reader123"),))
    conn.execute("UPDATE Customers SET login = 'maria', password_hash = ? WHERE id = 2",
                 (hash_password("maria123"),))
    conn.commit()
    conn.close()
    logging.info("База данных создана заново")


if __name__ == "__main__":
    setup_logging()
    if os.path.exists(DB_PATH):
        if input("Файл bookstore.db уже есть. Удалить и создать заново? (y/n): ").lower() != "y":
            raise SystemExit("Отмена.")
    init_db()
    print("База создана:", DB_PATH)
    print("Входы: owner/owner123, manager/manager123, reader/reader123, maria/maria123")
