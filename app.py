"""КнигаМир - приложение книжного магазина на Tkinter.

Запуск:  python app.py
Роли:    читатель (каталог, корзина, свои заказы),
         менеджер (книги, заказы, клиенты, отчёты, продажа в магазине),
         владелец (всё + удаление книг, сотрудники, журнал, резервные копии).
"""
import logging
import os
import sqlite3
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, simpledialog, ttk

import auth
import backup
import db
import repo
import reports
from auth import can


# ---------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------
def money(value):
    """Число -> строка с двумя знаками после запятой."""
    return "{:.2f}".format(value)


def make_table(parent, columns, headings, widths, height=None):
    """Создаёт таблицу (Treeview) с полосой прокрутки. Возвращает (рамка, таблица)."""
    box = ttk.Frame(parent)
    tree = ttk.Treeview(box, columns=columns, show="headings", selectmode="browse")
    if height is not None:
        tree.configure(height=height)
    scroll = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    for i, col in enumerate(columns):
        tree.heading(col, text=headings[i])
        tree.column(col, width=widths[i])
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return box, tree


def clear_tree(tree):
    tree.delete(*tree.get_children())


def show_error(where, error, parent=None):
    """Записывает ошибку в лог и показывает окно с текстом."""
    logging.error("%s: %s", where, error)
    messagebox.showerror("Ошибка", str(error), parent=parent)


def pick_id(box, items):
    """id выбранной строки в Combobox (или None, если ничего не выбрано)."""
    index = box.current()
    if index < 0:
        return None
    return items[index]["id"]


def select_by_id(box, items, item_id):
    """Выбирает в Combobox элемент с нужным id."""
    for i, item in enumerate(items):
        if item["id"] == item_id:
            box.current(i)


# ---------------------------------------------------------------
# Главное окно и переключение экранов
# ---------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("КнигаМир - книжный магазин")
        self.geometry("1150x680")
        self.minsize(900, 550)
        self.conn = db.connect()
        self.user = None      # сюда попадёт вошедший пользователь
        self.cart = {}        # корзина читателя: id книги -> количество
        self.frame = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    def show_frame(self, frame):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = frame
        self.frame.pack(fill="both", expand=True)

    def show_login(self):
        self.user = None
        self.cart = {}
        self.show_frame(LoginFrame(self))

    def show_main(self, user):
        self.user = user
        self.show_frame(MainFrame(self))

    def logout(self):
        logging.info("Выход из системы: %s", self.user["name"])
        self.show_login()

    def on_close(self):
        logging.info("Программа закрыта")
        self.conn.close()
        self.destroy()

    def report_callback_exception(self, exc, value, trace):
        """Любая неожиданная ошибка в окне попадает в лог."""
        logging.error("Необработанная ошибка", exc_info=(exc, value, trace))
        messagebox.showerror("Ошибка", "Произошла ошибка: " + str(value))


# ---------------------------------------------------------------
# Вход и регистрация
# ---------------------------------------------------------------
class LoginFrame(ttk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.fails = 0

        box = ttk.Frame(self)
        box.place(relx=0.5, rely=0.42, anchor="center")

        ttk.Label(box, text="КнигаМир", font=("Arial", 26, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 4))
        ttk.Label(box, text="Вход в систему").grid(row=1, column=0, columnspan=2, pady=(0, 15))

        ttk.Label(box, text="Логин:").grid(row=2, column=0, sticky="e", pady=4, padx=4)
        self.login_var = tk.StringVar()
        self.login_entry = ttk.Entry(box, textvariable=self.login_var, width=26)
        self.login_entry.grid(row=2, column=1, pady=4)

        ttk.Label(box, text="Пароль:").grid(row=3, column=0, sticky="e", pady=4, padx=4)
        self.pass_var = tk.StringVar()
        pass_entry = ttk.Entry(box, textvariable=self.pass_var, show="*", width=26)
        pass_entry.grid(row=3, column=1, pady=4)
        pass_entry.bind("<Return>", lambda event: self.do_login())

        self.login_button = ttk.Button(box, text="Войти", command=self.do_login)
        self.login_button.grid(row=4, column=0, columnspan=2, pady=(12, 4), sticky="ew")
        ttk.Button(box, text="Регистрация читателя", command=self.open_registration).grid(
            row=5, column=0, columnspan=2, sticky="ew")

        self.login_entry.focus()

    def do_login(self):
        name = self.login_var.get().strip()
        password = self.pass_var.get()
        if name == "" or password == "":
            messagebox.showwarning("Вход", "Введите логин и пароль")
            return

        user = auth.login(self.app.conn, name, password)
        if user is None:
            self.fails += 1
            logging.warning("Неудачная попытка входа: логин=%s (попытка %d)", name, self.fails)
            messagebox.showerror("Вход", "Неверный логин или пароль")
            self.pass_var.set("")
            if self.fails >= 3:  # после 3 ошибок блокируем кнопку на 5 секунд
                self.fails = 0
                self.login_button.config(state="disabled")
                self.after(5000, lambda: self.login_button.config(state="normal"))
                messagebox.showwarning("Вход", "Слишком много попыток. Подождите 5 секунд.")
            return

        logging.info("Вход в систему: %s (%s)", user["name"], user["role"])
        self.app.show_main(user)

    def open_registration(self):
        RegisterDialog(self, self.app, "самостоятельная регистрация", None)


class RegisterDialog(tk.Toplevel):
    """Форма нового клиента (читателя). Используется при входе и в разделе «Клиенты»."""

    FIELDS = [("ФИО:", "full_name"), ("Телефон:", "phone"), ("Email:", "email"),
              ("Адрес доставки:", "address"), ("Логин:", "login"),
              ("Пароль (от 6 символов):", "password"), ("Повтор пароля:", "password2")]

    def __init__(self, parent, app, who, on_done):
        super().__init__(parent)
        self.app = app
        self.who = who
        self.on_done = on_done
        self.title("Регистрация клиента")
        self.resizable(False, False)

        self.vars = {}
        for i, (label, key) in enumerate(self.FIELDS):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky="e", padx=8, pady=4)
            self.vars[key] = tk.StringVar()
            show = "*" if key.startswith("password") else ""
            ttk.Entry(self, textvariable=self.vars[key], width=34, show=show).grid(
                row=i, column=1, padx=8, pady=4)

        buttons = ttk.Frame(self)
        buttons.grid(row=len(self.FIELDS), column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="Зарегистрировать", command=self.save).pack(side="left", padx=5)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="left", padx=5)

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def save(self):
        v = {key: var.get() for key, var in self.vars.items()}
        if v["password"] != v["password2"]:
            messagebox.showerror("Ошибка", "Пароли не совпадают", parent=self)
            return
        try:
            customer_id = repo.CustomerRepository(self.app.conn).register(
                v["full_name"], v["phone"], v["email"], v["address"], v["login"], v["password"])
        except (ValueError, sqlite3.Error) as e:
            show_error("Регистрация", e, self)
            return
        repo.write_audit(self.app.conn, self.who, "Регистрация клиента",
                         "id=" + str(customer_id) + ", логин " + v["login"], "Customers")
        messagebox.showinfo("Готово", "Клиент зарегистрирован. Теперь можно войти.", parent=self)
        if self.on_done is not None:
            self.on_done()
        self.destroy()


# ---------------------------------------------------------------
# Основной экран с вкладками
# ---------------------------------------------------------------
class MainFrame(ttk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        role = app.user["role"]

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        text = "Пользователь: " + app.user["name"] + "   |   Роль: " + auth.ROLE_NAMES[role]
        ttk.Label(top, text=text, font=("Arial", 11, "bold")).pack(side="left")
        ttk.Button(top, text="Выйти", command=app.logout).pack(side="right")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.nb.add(CatalogTab(self.nb, app), text="Каталог")
        if can(role, "order_create"):
            self.nb.add(CartTab(self.nb, app), text="Корзина")
        orders_title = "Заказы" if can(role, "orders_all") else "Мои заказы"
        self.nb.add(OrdersTab(self.nb, app), text=orders_title)
        if can(role, "customers"):
            self.nb.add(CustomersTab(self.nb, app), text="Клиенты")
        if can(role, "reports"):
            self.nb.add(ReportsTab(self.nb, app), text="Отчёты")
        if can(role, "audit"):
            self.nb.add(AuditTab(self.nb, app), text="Журнал действий")
        if can(role, "staff"):
            self.nb.add(AdminTab(self.nb, app), text="Администрирование")

        self.nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.on_tab_changed(None)

    def on_tab_changed(self, event):
        """При переходе на вкладку обновляем её данные."""
        tab = self.nametowidget(self.nb.select())
        if hasattr(tab, "refresh"):
            tab.refresh()


# ---------------------------------------------------------------
# Вкладка «Каталог»
# ---------------------------------------------------------------
class CatalogTab(ttk.Frame):
    COLUMNS = ("title", "author", "category", "publisher", "isbn", "price", "stock_qty")
    HEADINGS = ("Название", "Автор", "Категория", "Издательство", "ISBN", "Цена, руб.", "В наличии")

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.books = repo.BookRepository(app.conn)
        self.categories = self.books.get_categories()
        role = app.user["role"]
        self.sort_col = "title"
        self.sort_desc = False

        # строка поиска
        top = ttk.Frame(self)
        top.pack(fill="x", padx=5, pady=6)
        ttk.Label(top, text="Название:").pack(side="left")
        self.title_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.title_var, width=20).pack(side="left", padx=4)
        ttk.Label(top, text="Автор:").pack(side="left")
        self.author_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.author_var, width=18).pack(side="left", padx=4)
        ttk.Label(top, text="Категория:").pack(side="left")
        names = ["Все категории"] + [c["name"] for c in self.categories]
        self.cat_box = ttk.Combobox(top, values=names, state="readonly", width=22)
        self.cat_box.current(0)
        self.cat_box.pack(side="left", padx=4)
        ttk.Button(top, text="Найти", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(top, text="Сбросить", command=self.reset).pack(side="left")

        # таблица
        widths = [230, 160, 150, 110, 120, 80, 80]
        box, self.tree = make_table(self, self.COLUMNS, self.HEADINGS, widths)
        box.pack(fill="both", expand=True, padx=5)
        for i, col in enumerate(self.COLUMNS):  # клик по заголовку - сортировка
            self.tree.heading(col, text=self.HEADINGS[i], command=lambda c=col: self.sort_by(c))
        self.tree.tag_configure("low", foreground="red")

        self.info = ttk.Label(self, text="")
        self.info.pack(anchor="w", padx=5, pady=(4, 0))

        # кнопки зависят от роли
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=5, pady=6)
        if can(role, "order_create"):
            ttk.Button(bottom, text="Добавить в корзину", command=self.add_to_cart).pack(side="left", padx=3)
        if can(role, "book_add"):
            ttk.Button(bottom, text="Добавить книгу", command=self.add_book).pack(side="left", padx=3)
        if can(role, "book_edit"):
            ttk.Button(bottom, text="Изменить", command=self.edit_book).pack(side="left", padx=3)
        if can(role, "sale"):
            ttk.Button(bottom, text="Продать в магазине", command=self.sell).pack(side="left", padx=3)
        if can(role, "book_delete"):
            ttk.Button(bottom, text="Удалить", command=self.delete_book).pack(side="left", padx=3)

    def reset(self):
        self.title_var.set("")
        self.author_var.set("")
        self.cat_box.current(0)
        self.refresh()

    def sort_by(self, column):
        if self.sort_col == column:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = column
            self.sort_desc = False
        self.refresh()

    def refresh(self):
        index = self.cat_box.current()
        category_id = None if index <= 0 else self.categories[index - 1]["id"]
        rows = self.books.get_books(self.title_var.get(), self.author_var.get(), category_id)

        def sort_key(row):
            value = row[self.sort_col]
            return value.lower() if isinstance(value, str) else value

        rows = sorted(rows, key=sort_key, reverse=self.sort_desc)
        clear_tree(self.tree)
        for r in rows:
            tags = ("low",) if r["stock_qty"] < 5 else ()
            self.tree.insert("", "end", iid=str(r["id"]), tags=tags, values=(
                r["title"], r["author"], r["category"], r["publisher"],
                r["isbn"], money(r["price"]), r["stock_qty"]))
        self.info.config(text="Найдено книг: " + str(len(rows))
                         + "   (красным выделены книги, которых осталось меньше 5)")

    def selected_id(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Каталог", "Сначала выберите книгу в таблице")
            return None
        return int(selection[0])

    def add_to_cart(self):
        book_id = self.selected_id()
        if book_id is None:
            return
        book = self.books.get_book_full(book_id)
        if book["stock_qty"] == 0:
            messagebox.showwarning("Корзина", "Этой книги нет в наличии")
            return
        in_cart = self.app.cart.get(book_id, 0)
        qty = simpledialog.askinteger(
            "В корзину", "Сколько экземпляров? (в наличии: " + str(book["stock_qty"]) + ")",
            parent=self, minvalue=1, maxvalue=book["stock_qty"])
        if qty is None:
            return
        if in_cart + qty > book["stock_qty"]:
            messagebox.showwarning("Корзина", "В корзине уже " + str(in_cart)
                                   + " шт. Всего в наличии: " + str(book["stock_qty"]))
            return
        self.app.cart[book_id] = in_cart + qty
        messagebox.showinfo("Корзина", "Добавлено: «" + book["title"] + "» - " + str(qty) + " шт.")

    def add_book(self):
        BookForm(self, self.app, None, self.refresh)

    def edit_book(self):
        book_id = self.selected_id()
        if book_id is not None:
            BookForm(self, self.app, book_id, self.refresh)

    def sell(self):
        book_id = self.selected_id()
        if book_id is None:
            return
        book = self.books.get_book_full(book_id)
        qty = simpledialog.askinteger(
            "Продажа в магазине", "«" + book["title"] + "»\nСколько экземпляров продать?",
            parent=self, minvalue=1)
        if qty is None:
            return
        try:
            total = self.books.add_sale(book_id, qty, self.app.user["employee_id"])
        except (ValueError, sqlite3.Error) as e:
            show_error("Продажа", e, self)
            return
        repo.write_audit(self.app.conn, self.app.user["name"], "Продажа в магазине",
                         "«" + book["title"] + "», " + str(qty) + " шт., " + money(total) + " руб.", "Sales")
        messagebox.showinfo("Продажа", "Продано. Сумма: " + money(total) + " руб.")
        self.refresh()

    def delete_book(self):
        book_id = self.selected_id()
        if book_id is None:
            return
        book = self.books.get_book_full(book_id)
        if not messagebox.askyesno("Удаление", "Удалить книгу «" + book["title"] + "»?"):
            return
        try:
            self.books.delete_book(book_id)
        except sqlite3.Error as e:  # например, по книге есть продажи - сработает триггер
            show_error("Удаление книги", e, self)
            return
        repo.write_audit(self.app.conn, self.app.user["name"], "Удалена книга",
                         "id=" + str(book_id) + ", «" + book["title"] + "»", "Books")
        self.refresh()


class BookForm(tk.Toplevel):
    """Окно добавления и изменения книги."""

    def __init__(self, parent, app, book_id, on_saved):
        super().__init__(parent)
        self.app = app
        self.book_id = book_id
        self.on_saved = on_saved
        self.books = repo.BookRepository(app.conn)
        self.title("Добавить книгу" if book_id is None else "Изменить книгу")
        self.resizable(False, False)

        self.authors = self.books.get_authors()
        self.categories = self.books.get_categories()
        self.publishers = self.books.get_publishers()

        self.title_var = tk.StringVar()
        self.isbn_var = tk.StringVar()
        self.price_var = tk.StringVar()
        self.stock_var = tk.StringVar(value="0")

        ttk.Label(self, text="Название:").grid(row=0, column=0, sticky="e", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.title_var, width=36).grid(row=0, column=1, padx=8)
        ttk.Label(self, text="Автор:").grid(row=1, column=0, sticky="e", padx=8, pady=4)
        self.author_box = ttk.Combobox(self, state="readonly", width=33,
                                       values=[a["full_name"] for a in self.authors])
        self.author_box.grid(row=1, column=1, padx=8)
        ttk.Label(self, text="Категория:").grid(row=2, column=0, sticky="e", padx=8, pady=4)
        self.cat_box = ttk.Combobox(self, state="readonly", width=33,
                                    values=[c["name"] for c in self.categories])
        self.cat_box.grid(row=2, column=1, padx=8)
        ttk.Label(self, text="Издательство:").grid(row=3, column=0, sticky="e", padx=8, pady=4)
        self.pub_box = ttk.Combobox(self, state="readonly", width=33,
                                    values=[p["name"] for p in self.publishers])
        self.pub_box.grid(row=3, column=1, padx=8)
        ttk.Label(self, text="ISBN (13 цифр):").grid(row=4, column=0, sticky="e", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.isbn_var, width=36).grid(row=4, column=1, padx=8)
        ttk.Label(self, text="Цена, руб.:").grid(row=5, column=0, sticky="e", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.price_var, width=36).grid(row=5, column=1, padx=8)
        ttk.Label(self, text="Количество на складе:").grid(row=6, column=0, sticky="e", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.stock_var, width=36).grid(row=6, column=1, padx=8)

        buttons = ttk.Frame(self)
        buttons.grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="Сохранить", command=self.save).pack(side="left", padx=5)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="left", padx=5)

        if book_id is not None:  # редактирование: заполняем поля
            book = self.books.get_book(book_id)
            self.title_var.set(book["title"])
            self.isbn_var.set(book["isbn"])
            self.price_var.set(str(book["price"]))
            self.stock_var.set(str(book["stock_qty"]))
            select_by_id(self.author_box, self.authors, book["author_id"])
            select_by_id(self.cat_box, self.categories, book["category_id"])
            select_by_id(self.pub_box, self.publishers, book["publisher_id"])

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def save(self):
        try:
            price = float(self.price_var.get().replace(",", "."))
            stock = int(self.stock_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Цена и количество должны быть числами", parent=self)
            return

        title = self.title_var.get()
        data = (title, self.isbn_var.get().strip(), price, stock,
                pick_id(self.author_box, self.authors),
                pick_id(self.cat_box, self.categories),
                pick_id(self.pub_box, self.publishers))

        errors = repo.check_book(*data)  # проверка ввода до обращения к БД
        if errors:
            messagebox.showerror("Проверьте данные", "\n".join(errors), parent=self)
            return

        try:
            if self.book_id is None:
                new_id = self.books.add_book(*data)
                repo.write_audit(self.app.conn, self.app.user["name"], "Добавлена книга",
                                 "id=" + str(new_id) + ", «" + title + "»", "Books")
            else:
                self.books.update_book(self.book_id, *data)
                repo.write_audit(self.app.conn, self.app.user["name"], "Изменена книга",
                                 "id=" + str(self.book_id) + ", «" + title + "»", "Books")
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e):
                e = "Книга с таким ISBN уже есть"
            show_error("Сохранение книги", e, self)
            return
        except (ValueError, sqlite3.Error) as e:
            show_error("Сохранение книги", e, self)
            return

        self.on_saved()
        self.destroy()


# ---------------------------------------------------------------
# Вкладка «Корзина» (читатель)
# ---------------------------------------------------------------
class CartTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.books = repo.BookRepository(app.conn)
        self.orders = repo.OrderRepository(app.conn)
        self.customers = repo.CustomerRepository(app.conn)

        columns = ("title", "qty", "price", "amount")
        headings = ("Книга", "Количество", "Цена, руб.", "Сумма, руб.")
        box, self.tree = make_table(self, columns, headings, [400, 100, 110, 110])
        box.pack(fill="both", expand=True, padx=5, pady=5)

        self.total_label = ttk.Label(self, text="", font=("Arial", 12, "bold"))
        self.total_label.pack(anchor="e", padx=10)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=5, pady=8)
        ttk.Button(bottom, text="Убрать выбранную", command=self.remove_item).pack(side="left", padx=3)
        ttk.Button(bottom, text="Очистить корзину", command=self.clear_cart).pack(side="left", padx=3)
        ttk.Button(bottom, text="Оформить заказ", command=self.checkout).pack(side="right", padx=3)

    def refresh(self):
        clear_tree(self.tree)
        total = 0
        for book_id in list(self.app.cart.keys()):
            book = self.books.get_book_full(book_id)
            if book is None:  # книгу успели удалить
                del self.app.cart[book_id]
                continue
            qty = self.app.cart[book_id]
            amount = qty * book["price"]
            total += amount
            self.tree.insert("", "end", iid=str(book_id),
                             values=(book["title"], qty, money(book["price"]), money(amount)))
        self.total_label.config(text="Итого: " + money(total) + " руб.")

    def remove_item(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Корзина", "Выберите книгу в таблице")
            return
        del self.app.cart[int(selection[0])]
        self.refresh()

    def clear_cart(self):
        self.app.cart.clear()
        self.refresh()

    def checkout(self):
        if len(self.app.cart) == 0:
            messagebox.showinfo("Корзина", "Корзина пуста")
            return
        customer_id = self.app.user["customer_id"]
        customer = self.customers.get(customer_id)

        address = simpledialog.askstring("Оформление заказа", "Адрес доставки:",
                                         initialvalue=customer["address"] or "", parent=self)
        if address is None:
            return
        if address.strip() == "":
            messagebox.showwarning("Оформление заказа", "Укажите адрес доставки")
            return
        phone = simpledialog.askstring("Оформление заказа", "Телефон для связи:",
                                       initialvalue=customer["phone"] or "", parent=self)
        if phone is None:
            return

        try:
            self.customers.update_contacts(customer_id, phone.strip(), address.strip())
            order_id = self.orders.create_order(customer_id, list(self.app.cart.items()))
        except (ValueError, sqlite3.Error) as e:
            show_error("Оформление заказа", e, self)
            self.refresh()
            return

        order = self.orders.get_order(order_id)
        repo.write_audit(self.app.conn, self.app.user["name"], "Оформлен заказ",
                         "заказ №" + str(order_id) + ", сумма " + money(order["total_amount"]), "Orders")
        self.app.cart.clear()
        self.refresh()
        messagebox.showinfo("Заказ оформлен", "Заказ №" + str(order_id) + " принят.\nСумма: "
                            + money(order["total_amount"]) + " руб.")


# ---------------------------------------------------------------
# Вкладка «Заказы»
# ---------------------------------------------------------------
class OrdersTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.orders = repo.OrderRepository(app.conn)
        self.see_all = can(app.user["role"], "orders_all")

        top = ttk.Frame(self)
        top.pack(fill="x", padx=5, pady=6)
        if self.see_all:
            ttk.Label(top, text="Статус:").pack(side="left")
            self.filter_box = ttk.Combobox(top, values=["Все"] + repo.ORDER_STATUSES,
                                           state="readonly", width=14)
            self.filter_box.current(0)
            self.filter_box.pack(side="left", padx=4)
            self.filter_box.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        ttk.Button(top, text="Обновить", command=self.refresh).pack(side="left", padx=4)

        columns = ("id", "date", "customer", "phone", "address", "status", "total")
        headings = ("№ заказа", "Дата", "Клиент", "Телефон", "Адрес доставки", "Статус", "Сумма, руб.")
        box, self.tree = make_table(self, columns, headings, [70, 130, 150, 120, 260, 90, 90], height=9)
        box.pack(fill="both", expand=True, padx=5)
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.show_items())

        ttk.Label(self, text="Состав выбранного заказа:").pack(anchor="w", padx=5, pady=(8, 0))
        item_columns = ("title", "qty", "price", "amount")
        item_headings = ("Книга", "Количество", "Цена, руб.", "Сумма, руб.")
        box2, self.items_tree = make_table(self, item_columns, item_headings, [400, 100, 110, 110], height=5)
        box2.pack(fill="both", expand=True, padx=5)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=5, pady=8)
        if self.see_all:
            ttk.Label(bottom, text="Новый статус:").pack(side="left")
            self.status_box = ttk.Combobox(bottom, values=repo.ORDER_STATUSES, state="readonly", width=14)
            self.status_box.pack(side="left", padx=4)
            ttk.Button(bottom, text="Сменить статус", command=self.change_status).pack(side="left", padx=4)
        else:
            ttk.Button(bottom, text="Отменить заказ", command=self.cancel_own).pack(side="left")

    def refresh(self):
        customer_id = None if self.see_all else self.app.user["customer_id"]
        status = None
        if self.see_all and self.filter_box.current() > 0:
            status = repo.ORDER_STATUSES[self.filter_box.current() - 1]
        clear_tree(self.tree)
        clear_tree(self.items_tree)
        for o in self.orders.get_orders(customer_id, status):
            self.tree.insert("", "end", iid=str(o["id"]), values=(
                o["id"], o["order_date"], o["customer"], o["phone"], o["address"],
                o["status"], money(o["total_amount"])))

    def selected_id(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Заказы", "Сначала выберите заказ в таблице")
            return None
        return int(selection[0])

    def show_items(self):
        selection = self.tree.selection()
        clear_tree(self.items_tree)
        if not selection:
            return
        for item in self.orders.get_items(int(selection[0])):
            self.items_tree.insert("", "end", values=(
                item["title"], item["qty"], money(item["price"]), money(item["amount"])))

    def change_status(self):
        order_id = self.selected_id()
        if order_id is None:
            return
        index = self.status_box.current()
        if index < 0:
            messagebox.showinfo("Заказы", "Выберите новый статус")
            return
        new_status = repo.ORDER_STATUSES[index]
        old_status = self.orders.get_order(order_id)["status"]
        try:
            self.orders.set_status(order_id, new_status)
        except (ValueError, sqlite3.Error) as e:
            show_error("Смена статуса", e, self)
            return
        repo.write_audit(self.app.conn, self.app.user["name"], "Смена статуса заказа",
                         "заказ №" + str(order_id) + ": " + old_status + " -> " + new_status, "Orders")
        self.refresh()

    def cancel_own(self):
        order_id = self.selected_id()
        if order_id is None:
            return
        order = self.orders.get_order(order_id)
        if order["status"] != "Новый":
            messagebox.showinfo("Заказы", "Отменить можно только заказ со статусом «Новый»")
            return
        if not messagebox.askyesno("Отмена заказа", "Отменить заказ №" + str(order_id) + "?"):
            return
        try:
            self.orders.set_status(order_id, "Отменён")
        except sqlite3.Error as e:
            show_error("Отмена заказа", e, self)
            return
        repo.write_audit(self.app.conn, self.app.user["name"], "Отмена заказа",
                         "заказ №" + str(order_id), "Orders")
        self.refresh()


# ---------------------------------------------------------------
# Вкладка «Клиенты» (менеджер, владелец)
# ---------------------------------------------------------------
class CustomersTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.customers = repo.CustomerRepository(app.conn)

        columns = ("id", "name", "phone", "email", "address", "login", "date")
        headings = ("ID", "ФИО", "Телефон", "Email", "Адрес доставки", "Логин", "Дата регистрации")
        box, self.tree = make_table(self, columns, headings, [40, 160, 120, 170, 280, 80, 110])
        box.pack(fill="both", expand=True, padx=5, pady=5)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=5, pady=6)
        ttk.Button(bottom, text="Добавить клиента", command=self.add_customer).pack(side="left", padx=3)
        ttk.Button(bottom, text="Изменить телефон и адрес", command=self.edit_contacts).pack(side="left", padx=3)

    def refresh(self):
        clear_tree(self.tree)
        for c in self.customers.get_all():
            self.tree.insert("", "end", iid=str(c["id"]), values=(
                c["id"], c["full_name"], c["phone"], c["email"], c["address"],
                c["login"], c["registration_date"]))

    def add_customer(self):
        RegisterDialog(self, self.app, self.app.user["name"], self.refresh)

    def edit_contacts(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Клиенты", "Выберите клиента в таблице")
            return
        customer_id = int(selection[0])
        customer = self.customers.get(customer_id)
        phone = simpledialog.askstring("Клиент", "Телефон:", initialvalue=customer["phone"] or "", parent=self)
        if phone is None:
            return
        address = simpledialog.askstring("Клиент", "Адрес доставки:", initialvalue=customer["address"] or "", parent=self)
        if address is None:
            return
        self.customers.update_contacts(customer_id, phone.strip(), address.strip())
        repo.write_audit(self.app.conn, self.app.user["name"], "Изменены контакты клиента",
                         "id=" + str(customer_id), "Customers")
        self.refresh()


# ---------------------------------------------------------------
# Вкладка «Отчёты» (менеджер, владелец)
# ---------------------------------------------------------------
class ReportsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.headers = []
        self.rows = []

        top = ttk.Frame(self)
        top.pack(fill="x", padx=5, pady=6)
        ttk.Label(top, text="Отчёт:").pack(side="left")
        self.report_box = ttk.Combobox(top, values=reports.REPORT_NAMES, state="readonly", width=22)
        self.report_box.current(0)
        self.report_box.pack(side="left", padx=4)
        ttk.Label(top, text="с (ГГГГ-ММ-ДД):").pack(side="left", padx=(10, 0))
        self.start_var = tk.StringVar(value="2026-01-01")
        ttk.Entry(top, textvariable=self.start_var, width=12).pack(side="left", padx=4)
        ttk.Label(top, text="по:").pack(side="left")
        self.end_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(top, textvariable=self.end_var, width=12).pack(side="left", padx=4)
        ttk.Button(top, text="Показать", command=self.show).pack(side="left", padx=6)
        ttk.Button(top, text="Сохранить в CSV", command=self.save).pack(side="left")

        self.box = None
        self.tree = None

    def show(self):
        name = self.report_box.get()
        start = self.start_var.get().strip()
        end = self.end_var.get().strip()
        if name == "Продажи за период":
            try:
                datetime.strptime(start, "%Y-%m-%d")
                datetime.strptime(end, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Отчёт", "Даты вводятся в формате ГГГГ-ММ-ДД, например 2026-09-30")
                return

        self.headers, self.rows = reports.get_report(self.app.conn, name, start, end)

        if self.box is not None:  # у каждого отчёта свои столбцы - создаём таблицу заново
            self.box.destroy()
        column_ids = ["c" + str(i) for i in range(len(self.headers))]
        widths = [150] * len(self.headers)
        self.box, self.tree = make_table(self, column_ids, self.headers, widths)
        self.box.pack(fill="both", expand=True, padx=5, pady=5)
        for row in self.rows:
            values = [money(v) if isinstance(v, float) else v for v in row]
            self.tree.insert("", "end", values=values)

    def save(self):
        if len(self.rows) == 0:
            messagebox.showinfo("Отчёт", "Сначала нажмите «Показать»")
            return
        path = reports.save_csv(self.report_box.get(), self.headers, self.rows)
        repo.write_audit(self.app.conn, self.app.user["name"], "Экспорт отчёта", os.path.basename(path))
        messagebox.showinfo("Отчёт", "Файл сохранён:\n" + path)


# ---------------------------------------------------------------
# Вкладка «Журнал действий» (владелец)
# ---------------------------------------------------------------
class AuditTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        columns = ("date", "user", "operation", "details")
        headings = ("Дата и время", "Пользователь", "Действие", "Подробности")
        box, self.tree = make_table(self, columns, headings, [150, 150, 190, 500])
        box.pack(fill="both", expand=True, padx=5, pady=5)
        ttk.Label(self, text="Показаны последние 300 записей. Подробный технический журнал - в файле app.log.").pack(
            anchor="w", padx=5)

    def refresh(self):
        clear_tree(self.tree)
        rows = self.app.conn.execute(
            "SELECT changed_at, user_name, operation, details FROM AuditLog "
            "ORDER BY id DESC LIMIT 300").fetchall()
        for r in rows:
            self.tree.insert("", "end", values=(r["changed_at"], r["user_name"] or "система",
                                                r["operation"], r["details"]))


# ---------------------------------------------------------------
# Вкладка «Администрирование» (владелец): сотрудники и резервные копии
# ---------------------------------------------------------------
class AdminTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.staff = repo.EmployeeRepository(app.conn)

        staff_frame = ttk.LabelFrame(self, text="Сотрудники")
        staff_frame.pack(fill="both", expand=True, padx=8, pady=8)
        columns = ("id", "name", "login", "role")
        headings = ("ID", "ФИО", "Логин", "Роль")
        box, self.tree = make_table(staff_frame, columns, headings, [50, 250, 150, 120], height=6)
        box.pack(fill="both", expand=True, padx=5, pady=5)
        ttk.Button(staff_frame, text="Добавить сотрудника", command=self.add_staff).pack(anchor="w", padx=5, pady=5)

        backup_frame = ttk.LabelFrame(self, text="Резервное копирование")
        backup_frame.pack(fill="x", padx=8, pady=8)
        ttk.Button(backup_frame, text="Создать резервную копию", command=self.make_backup).pack(
            side="left", padx=5, pady=8)
        ttk.Button(backup_frame, text="Восстановить из копии...", command=self.restore).pack(
            side="left", padx=5, pady=8)

    def refresh(self):
        clear_tree(self.tree)
        for e in self.staff.get_all():
            self.tree.insert("", "end", values=(e["id"], e["full_name"], e["login"],
                                                auth.ROLE_NAMES[e["role"]]))

    def add_staff(self):
        StaffDialog(self, self.app, self.refresh)

    def make_backup(self):
        try:
            path = backup.make_backup()
        except Exception as e:
            show_error("Резервная копия", e, self)
            return
        repo.write_audit(self.app.conn, self.app.user["name"], "Резервная копия", os.path.basename(path))
        messagebox.showinfo("Резервная копия", "Копия создана:\n" + path)

    def restore(self):
        folder = backup.BACKUP_DIR if os.path.isdir(backup.BACKUP_DIR) else db.BASE_DIR
        path = filedialog.askopenfilename(title="Выберите файл резервной копии", initialdir=folder,
                                          filetypes=[("Файлы базы данных", "*.db")])
        if path == "":
            return
        if not messagebox.askyesno("Восстановление",
                                   "Текущая база будет заменена данными из копии.\nПродолжить?"):
            return
        try:
            self.app.conn.commit()
            backup.restore_backup(path)
        except Exception as e:
            show_error("Восстановление", e, self)
            return
        messagebox.showinfo("Восстановление", "База восстановлена. Войдите в систему заново.")
        self.app.show_login()


class StaffDialog(tk.Toplevel):
    def __init__(self, parent, app, on_done):
        super().__init__(parent)
        self.app = app
        self.on_done = on_done
        self.title("Новый сотрудник")
        self.resizable(False, False)

        self.name_var = tk.StringVar()
        self.login_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        rows = [("ФИО:", self.name_var, ""), ("Логин:", self.login_var, ""),
                ("Пароль (от 6 символов):", self.pass_var, "*")]
        for i, (label, var, show) in enumerate(rows):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky="e", padx=8, pady=4)
            ttk.Entry(self, textvariable=var, width=30, show=show).grid(row=i, column=1, padx=8)
        ttk.Label(self, text="Роль:").grid(row=3, column=0, sticky="e", padx=8, pady=4)
        self.role_box = ttk.Combobox(self, values=["Менеджер", "Владелец"], state="readonly", width=27)
        self.role_box.current(0)
        self.role_box.grid(row=3, column=1, padx=8)

        buttons = ttk.Frame(self)
        buttons.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="Добавить", command=self.save).pack(side="left", padx=5)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="left", padx=5)

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def save(self):
        role = "manager" if self.role_box.current() == 0 else "owner"
        try:
            repo.EmployeeRepository(self.app.conn).add(
                self.name_var.get(), self.login_var.get(), self.pass_var.get(), role)
        except (ValueError, sqlite3.Error) as e:
            show_error("Добавление сотрудника", e, self)
            return
        repo.write_audit(self.app.conn, self.app.user["name"], "Добавлен сотрудник",
                         self.login_var.get() + " (" + role + ")", "Employees")
        self.on_done()
        self.destroy()


# ---------------------------------------------------------------
def main():
    db.setup_logging()
    if not os.path.exists(db.DB_PATH):  # первый запуск: создаём базу
        db.init_db()
    logging.info("Программа запущена")
    App().mainloop()


if __name__ == "__main__":
    main()
