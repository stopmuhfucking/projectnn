"""Проверка работы БД, входа, заказов и ролей без графического интерфейса."""
import os
import sqlite3
import tempfile

import auth
import backup
import db
import repo
import reports

# Тесты работают с временной БД, чтобы не трогать настоящую
db.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
db.setup_logging()
db.init_db()
conn = db.connect()
ok = 0


def check(name, condition):
    global ok
    print(("OK   " if condition else "FAIL ") + name)
    if not condition:
        raise SystemExit(1)
    ok += 1


# ----- вход и роли -----
check("владелец входит", auth.login(conn, "owner", "owner123")["role"] == "owner")
check("менеджер входит", auth.login(conn, "manager", "manager123")["role"] == "manager")
u = auth.login(conn, "reader", "reader123")
check("читатель входит", u["role"] == "reader" and u["customer_id"] == 1)
check("неверный пароль отклонён", auth.login(conn, "owner", "qwerty") is None)
check("SQL-инъекция в логине не работает", auth.login(conn, "' OR 1=1 --", "x") is None)
check("пароль в БД хранится хешем", "owner123" not in conn.execute(
    "SELECT password_hash FROM Employees WHERE login='owner'").fetchone()[0])
check("права: читатель не добавляет книги", not auth.can("reader", "book_add"))
check("права: менеджер добавляет, но не удаляет", auth.can("manager", "book_add")
      and not auth.can("manager", "book_delete"))
check("права: владелец может всё", auth.can("owner", "book_delete") and auth.can("owner", "backup"))

# ----- книги -----
books = repo.BookRepository(conn)
check("в каталоге 7 книг", len(books.get_books()) == 7)
check("поиск по названию", len(books.get_books(title="война")) == 1)
check("поиск по автору", len(books.get_books(author="Достоевский")) == 2)
new_id = books.add_book("Тестовая книга", "9785170000999", 300, 5, 1, 1, 1)
check("книга добавлена", books.get_book(new_id)["title"] == "Тестовая книга")
try:
    books.add_book("", "123", -5, 0, 1, 1, 1)
    check("проверка данных книги", False)
except ValueError:
    check("проверка данных книги (пусто, ISBN, цена)", True)
try:
    books.add_book("Дубль", "9785170000999", 300, 5, 1, 1, 1)
    check("дубль ISBN", False)
except sqlite3.IntegrityError:
    check("дубль ISBN отклонён базой", True)
books.update_book(new_id, "Тестовая книга 2", "9785170000999", 350, 6, 1, 1, 1)
check("книга изменена", books.get_book(new_id)["price"] == 350)
books.delete_book(new_id)
check("книга без продаж удалена", books.get_book(new_id) is None)
try:
    books.delete_book(1)
    check("удаление книги с продажами", False)
except sqlite3.Error as e:
    check("книгу с продажами удалить нельзя: " + str(e), True)

# ----- заказы -----
orders = repo.OrderRepository(conn)
stock_before = books.get_book(1)["stock_qty"]
order_id = orders.create_order(1, [(1, 2), (2, 1)])
o = orders.get_order(order_id)
check("заказ создан, статус «Новый»", o["status"] == "Новый")
check("сумма заказа посчитана триггером (2*850 + 650)", o["total_amount"] == 2350)
check("остаток списан триггером", books.get_book(1)["stock_qty"] == stock_before - 2)
check("в заказе 2 позиции", len(orders.get_items(order_id)) == 2)
check("клиент видит только свои заказы", all(r["customer_id"] == 1 for r in orders.get_orders(customer_id=1)))

try:
    orders.create_order(1, [(7, 1), (1, 9999)])
    check("заказ больше остатка", False)
except ValueError:
    check("заказ больше остатка отклонён", True)
check("неудачный заказ не оставил следов (откат)", len(orders.get_orders()) == 4)

orders.set_status(order_id, "Собран")
check("статус изменён", orders.get_order(order_id)["status"] == "Собран")
orders.set_status(order_id, "Отменён")
check("отмена вернула книги на склад", books.get_book(1)["stock_qty"] == stock_before)
try:
    orders.set_status(order_id, "Новый")
    check("оживление отменённого", False)
except sqlite3.Error:
    check("отменённый заказ изменить нельзя", True)

# ----- клиенты и сотрудники -----
customers = repo.CustomerRepository(conn)
cid = customers.register("Новый Клиент", "+7 900 000-00-00", "new@example.ru", "г. Тула", "newbie", "secret1")
check("клиент зарегистрирован и может войти", auth.login(conn, "newbie", "secret1")["customer_id"] == cid)
try:
    customers.register("Ещё", "", "x@example.ru", "", "owner", "secret1")
    check("занятый логин", False)
except ValueError:
    check("логин, занятый сотрудником, отклонён", True)
repo.EmployeeRepository(conn).add("Второй менеджер", "manager2", "pass1234", "manager")
check("новый сотрудник входит", auth.login(conn, "manager2", "pass1234")["role"] == "manager")

# ----- журнал и отчёты -----
repo.write_audit(conn, "owner", "Тест", "проверка журнала")
check("запись в журнале действий", conn.execute("SELECT COUNT(*) FROM AuditLog WHERE user_name='owner'").fetchone()[0] == 1)
h, rows = reports.get_report(conn, "Продажи за период", "2026-01-01", "2026-12-31")
check("отчёт по продажам с итогом", rows[-1][1] == "ИТОГО" and rows[-1][4] > 0)
h, rows = reports.get_report(conn, "Топ-10 книг", "", "")
check("топ-10 не пустой", len(rows) > 0)
h, rows = reports.get_report(conn, "Остатки на складе", "", "")
check("остатки на складе", rows[-1][0] == "ИТОГО")
path = reports.save_csv("Тест", h, rows)
check("CSV сохранён", os.path.exists(path))

# ----- резервная копия -----
backup.BACKUP_DIR = os.path.join(tempfile.mkdtemp(), "b")
db.DB_PATH = db.DB_PATH  # (копия делается из тестовой БД)
copy_path = backup.make_backup()
check("резервная копия создана и проверена", backup.check_file(copy_path))

print("\nВсе проверки пройдены:", ok)
