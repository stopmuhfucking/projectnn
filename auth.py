"""Вход в систему: пароли (соль + SHA-256), роли и права."""
import hashlib
import os

# Права каждой роли
PERMISSIONS = {
    # читатель: смотрит каталог, оформляет и отменяет свои заказы
    "reader":  {"order_create"},
    # менеджер: книги (добавить/изменить), заказы, клиенты, отчёты, продажа в магазине
    "manager": {"book_add", "book_edit", "sale", "orders_all", "customers", "reports"},
    # владелец: всё, что у менеджера, плюс удаление книг, сотрудники, журнал, резервные копии
    "owner":   {"book_add", "book_edit", "book_delete", "sale", "orders_all",
                "customers", "reports", "audit", "staff", "backup"},
}

ROLE_NAMES = {"reader": "Читатель", "manager": "Менеджер", "owner": "Владелец"}


def can(role, action):
    """Разрешено ли этой роли действие."""
    return action in PERMISSIONS.get(role, set())


def hash_password(password):
    """Возвращает строку 'соль$хеш'. Пароль в открытом виде нигде не хранится."""
    salt = os.urandom(8).hex()
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return salt + "$" + h


def check_password(password, stored):
    """Проверяет пароль. Если в БД лежит что-то не то (например, demo_hash) - False."""
    if not stored or "$" not in stored:
        return False
    salt, h = stored.split("$", 1)
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == h


def login(conn, login_name, password):
    """Ищет пользователя сначала среди сотрудников, потом среди клиентов.

    Возвращает словарь с данными пользователя или None.
    """
    row = conn.execute(
        "SELECT id, full_name, role, password_hash FROM Employees WHERE login = ?",
        (login_name,)).fetchone()
    if row is not None and check_password(password, row["password_hash"]):
        return {"name": row["full_name"], "role": row["role"],
                "employee_id": row["id"], "customer_id": None}

    row = conn.execute(
        "SELECT id, full_name, password_hash FROM Customers WHERE login = ?",
        (login_name,)).fetchone()
    if row is not None and check_password(password, row["password_hash"]):
        return {"name": row["full_name"], "role": "reader",
                "employee_id": None, "customer_id": row["id"]}
    return None
