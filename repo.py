"""Доступ к данным (аналог репозиториев ADO.NET): книги, клиенты, сотрудники, заказы."""
import logging
import sqlite3
from datetime import date

from auth import hash_password

ORDER_STATUSES = ["Новый", "Собран", "Отправлен", "Доставлен", "Отменён"]


def write_audit(conn, user_name, operation, details, table_name="App"):
    """Запись в журнал действий (таблица AuditLog) + в файл app.log."""
    with conn:
        conn.execute(
            "INSERT INTO AuditLog (table_name, operation, details, user_name) VALUES (?, ?, ?, ?)",
            (table_name, operation, details, user_name))
    logging.info("%s | %s | %s", user_name, operation, details)


def check_book(title, isbn, price, stock, author_id, category_id, publisher_id):
    """Проверка данных книги. Возвращает список ошибок."""
    errors = []
    if title.strip() == "":
        errors.append("Название обязательно")
    if not (isbn.isdigit() and len(isbn) == 13):
        errors.append("ISBN - ровно 13 цифр")
    if price <= 0:
        errors.append("Цена должна быть больше 0")
    if stock < 0:
        errors.append("Остаток не может быть отрицательным")
    if author_id is None or category_id is None or publisher_id is None:
        errors.append("Выберите автора, категорию и издательство")
    return errors


class BookRepository:
    def __init__(self, conn):
        self.conn = conn

    def get_books(self, title="", author="", category_id=None):
        """Список книг из представления v_BooksFull (параметризованный запрос)."""
        sql = ("SELECT v.* FROM v_BooksFull v JOIN Books b ON b.id = v.id "
               "WHERE lower_ru(v.title) LIKE ? AND lower_ru(v.author) LIKE ?")
        params = ["%" + title.lower() + "%", "%" + author.lower() + "%"]
        if category_id is not None:
            sql += " AND b.category_id = ?"
            params.append(category_id)
        return self.conn.execute(sql + " ORDER BY v.title", params).fetchall()

    def get_book(self, book_id):
        """Одна книга из таблицы Books (для формы редактирования)."""
        return self.conn.execute("SELECT * FROM Books WHERE id = ?", (book_id,)).fetchone()

    def get_book_full(self, book_id):
        return self.conn.execute("SELECT * FROM v_BooksFull WHERE id = ?", (book_id,)).fetchone()

    def get_authors(self):
        return self.conn.execute("SELECT id, full_name FROM Authors ORDER BY full_name").fetchall()

    def get_categories(self):
        return self.conn.execute("SELECT id, name FROM Categories ORDER BY name").fetchall()

    def get_publishers(self):
        return self.conn.execute("SELECT id, name FROM Publishers ORDER BY name").fetchall()

    def add_book(self, title, isbn, price, stock, author_id, category_id, publisher_id):
        errors = check_book(title, isbn, price, stock, author_id, category_id, publisher_id)
        if errors:
            raise ValueError("; ".join(errors))
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO Books (title, author_id, category_id, isbn, price, stock_qty, "
                "publisher_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title.strip(), author_id, category_id, isbn, price, stock, publisher_id))
        return cur.lastrowid

    def update_book(self, book_id, title, isbn, price, stock, author_id, category_id, publisher_id):
        errors = check_book(title, isbn, price, stock, author_id, category_id, publisher_id)
        if errors:
            raise ValueError("; ".join(errors))
        with self.conn:
            self.conn.execute(
                "UPDATE Books SET title = ?, author_id = ?, category_id = ?, isbn = ?, "
                "price = ?, stock_qty = ?, publisher_id = ? WHERE id = ?",
                (title.strip(), author_id, category_id, isbn, price, stock, publisher_id, book_id))

    def delete_book(self, book_id):
        """Если у книги есть продажи или заказы - сработает триггер и удаление отменится."""
        with self.conn:
            self.conn.execute("DELETE FROM Books WHERE id = ?", (book_id,))

    def add_sale(self, book_id, qty, employee_id):
        """Продажа в магазине. Остаток списывает триггер tr_Sales_Insert."""
        book = self.conn.execute("SELECT price FROM Books WHERE id = ?", (book_id,)).fetchone()
        if book is None:
            raise ValueError("Книга не найдена")
        with self.conn:
            self.conn.execute(
                "INSERT INTO Sales (book_id, qty, total_price, employee_id) VALUES (?, ?, ?, ?)",
                (book_id, qty, book["price"] * qty, employee_id))
        return book["price"] * qty


class CustomerRepository:
    def __init__(self, conn):
        self.conn = conn

    def login_exists(self, login_name):
        """Логин должен быть уникальным и среди клиентов, и среди сотрудников."""
        a = self.conn.execute("SELECT 1 FROM Customers WHERE login = ?", (login_name,)).fetchone()
        b = self.conn.execute("SELECT 1 FROM Employees WHERE login = ?", (login_name,)).fetchone()
        return a is not None or b is not None

    def register(self, full_name, phone, email, address, login_name, password):
        """Регистрация клиента (читателя). Возвращает id клиента."""
        if full_name.strip() == "":
            raise ValueError("Введите ФИО")
        if "@" not in email:
            raise ValueError("Введите правильный email")
        if login_name.strip() == "":
            raise ValueError("Введите логин")
        if len(password) < 6:
            raise ValueError("Пароль должен быть не короче 6 символов")
        if self.login_exists(login_name):
            raise ValueError("Такой логин уже занят")
        try:
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO Customers (full_name, phone, email, address, login, password_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (full_name.strip(), phone, email.strip(), address, login_name.strip(),
                     hash_password(password)))
            return cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("Клиент с таким email уже есть")

    def get_all(self):
        return self.conn.execute(
            "SELECT id, full_name, phone, email, address, login, registration_date "
            "FROM Customers ORDER BY full_name").fetchall()

    def get(self, customer_id):
        return self.conn.execute("SELECT * FROM Customers WHERE id = ?", (customer_id,)).fetchone()

    def update_contacts(self, customer_id, phone, address):
        with self.conn:
            self.conn.execute("UPDATE Customers SET phone = ?, address = ? WHERE id = ?",
                              (phone, address, customer_id))


class EmployeeRepository:
    def __init__(self, conn):
        self.conn = conn

    def get_all(self):
        return self.conn.execute(
            "SELECT id, full_name, login, role FROM Employees ORDER BY id").fetchall()

    def add(self, full_name, login_name, password, role):
        if full_name.strip() == "" or login_name.strip() == "":
            raise ValueError("Введите ФИО и логин")
        if len(password) < 6:
            raise ValueError("Пароль должен быть не короче 6 символов")
        if role not in ("manager", "owner"):
            raise ValueError("Неверная роль")
        if CustomerRepository(self.conn).login_exists(login_name):
            raise ValueError("Такой логин уже занят")
        with self.conn:
            self.conn.execute(
                "INSERT INTO Employees (full_name, role, login, password_hash) VALUES (?, ?, ?, ?)",
                (full_name.strip(), role, login_name.strip(), hash_password(password)))


class OrderRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_order(self, customer_id, items):
        """Создаёт заказ. items - список пар (book_id, количество).

        Всё выполняется в одной транзакции: если хоть одной книги не хватает,
        заказ не создаётся совсем. Остаток и сумму заказа считают триггеры.
        """
        if len(items) == 0:
            raise ValueError("Корзина пуста")
        with self.conn:
            cur = self.conn.execute("INSERT INTO Orders (customer_id) VALUES (?)", (customer_id,))
            order_id = cur.lastrowid
            for book_id, qty in items:
                book = self.conn.execute(
                    "SELECT title, price, stock_qty FROM Books WHERE id = ?", (book_id,)).fetchone()
                if book is None:
                    raise ValueError("Книга не найдена")
                if qty > book["stock_qty"]:
                    raise ValueError("Книги «" + book["title"] + "»: на складе только "
                                     + str(book["stock_qty"]) + " шт.")
                self.conn.execute(
                    "INSERT INTO OrderItems (order_id, book_id, qty, price) VALUES (?, ?, ?, ?)",
                    (order_id, book_id, qty, book["price"]))
        return order_id

    def get_orders(self, customer_id=None, status=None):
        """Все заказы (для менеджера/владельца) или заказы одного клиента."""
        sql = "SELECT * FROM v_OrdersFull WHERE 1 = 1"
        params = []
        if customer_id is not None:
            sql += " AND customer_id = ?"
            params.append(customer_id)
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        return self.conn.execute(sql + " ORDER BY id DESC", params).fetchall()

    def get_order(self, order_id):
        return self.conn.execute("SELECT * FROM v_OrdersFull WHERE id = ?", (order_id,)).fetchone()

    def get_items(self, order_id):
        return self.conn.execute(
            "SELECT b.title, oi.qty, oi.price, oi.qty * oi.price AS amount "
            "FROM OrderItems oi JOIN Books b ON b.id = oi.book_id "
            "WHERE oi.order_id = ? ORDER BY oi.id", (order_id,)).fetchall()

    def set_status(self, order_id, status):
        if status not in ORDER_STATUSES:
            raise ValueError("Неверный статус")
        with self.conn:
            self.conn.execute("UPDATE Orders SET status = ? WHERE id = ?", (status, order_id))
