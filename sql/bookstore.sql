-- =====================================================
-- КнигаМир: схема БД (SQLite), версия 2
-- Что добавлено к прежней схеме:
--   * Customers: адрес доставки, логин и пароль (читатели входят в приложение)
--   * Orders и OrderItems: заказы из магазина
--   * роли сотрудников: owner (владелец) и manager (менеджер)
--   * v_AllSales: продажи в магазине + заказы (для отчётов)
-- =====================================================
PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS v_BooksFull;
DROP VIEW IF EXISTS v_AllSales;
DROP VIEW IF EXISTS v_SalesReport;
DROP VIEW IF EXISTS v_StockBalance;
DROP VIEW IF EXISTS v_OrdersFull;

DROP TABLE IF EXISTS AuditLog;
DROP TABLE IF EXISTS SupplyItems;
DROP TABLE IF EXISTS SupplyOrders;
DROP TABLE IF EXISTS OrderItems;
DROP TABLE IF EXISTS Orders;
DROP TABLE IF EXISTS Sales;
DROP TABLE IF EXISTS Employees;
DROP TABLE IF EXISTS Customers;
DROP TABLE IF EXISTS Books;
DROP TABLE IF EXISTS Suppliers;
DROP TABLE IF EXISTS Categories;
DROP TABLE IF EXISTS Publishers;
DROP TABLE IF EXISTS Authors;

CREATE TABLE Authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    birth_year INTEGER,
    country TEXT
);

CREATE TABLE Categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    parent_id INTEGER,
    FOREIGN KEY (parent_id) REFERENCES Categories(id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE Publishers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    phone TEXT
);

CREATE TABLE Suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT
);

-- Клиенты (они же «читатели»: у кого есть логин, тот может войти в приложение)
CREATE TABLE Customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT,
    email TEXT UNIQUE,
    address TEXT,
    login TEXT UNIQUE,
    password_hash TEXT,
    registration_date TEXT NOT NULL DEFAULT CURRENT_DATE
);

-- Сотрудники
CREATE TABLE Employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'manager')),
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE Books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    isbn TEXT NOT NULL UNIQUE CHECK (length(isbn) = 13 AND isbn NOT GLOB '*[^0-9]*'),
    price REAL NOT NULL CHECK (price > 0),
    stock_qty INTEGER NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    publisher_id INTEGER NOT NULL,
    FOREIGN KEY (author_id)    REFERENCES Authors(id)    ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (category_id)  REFERENCES Categories(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (publisher_id) REFERENCES Publishers(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Продажи в самом магазине (у кассы)
CREATE TABLE Sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    customer_id INTEGER,
    sale_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    qty INTEGER NOT NULL CHECK (qty > 0),
    total_price REAL NOT NULL CHECK (total_price > 0),
    employee_id INTEGER,
    FOREIGN KEY (book_id)     REFERENCES Books(id)     ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES Customers(id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (employee_id) REFERENCES Employees(id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- Заказы клиентов: номер заказа, дата, клиент, статус, сумма
CREATE TABLE Orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    customer_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Новый'
        CHECK (status IN ('Новый', 'Собран', 'Отправлен', 'Доставлен', 'Отменён')),
    total_amount REAL NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    FOREIGN KEY (customer_id) REFERENCES Customers(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Состав заказа: заказ, книга, количество, цена (цена на момент заказа)
CREATE TABLE OrderItems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    qty INTEGER NOT NULL CHECK (qty > 0),
    price REAL NOT NULL CHECK (price > 0),
    FOREIGN KEY (order_id) REFERENCES Orders(id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (book_id)  REFERENCES Books(id)  ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE SupplyOrders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    order_date TEXT NOT NULL DEFAULT CURRENT_DATE,
    total_amount REAL NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'received', 'cancelled')),
    FOREIGN KEY (supplier_id) REFERENCES Suppliers(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE SupplyItems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supply_order_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    qty INTEGER NOT NULL CHECK (qty > 0),
    unit_price REAL NOT NULL CHECK (unit_price > 0),
    FOREIGN KEY (supply_order_id) REFERENCES SupplyOrders(id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (book_id)         REFERENCES Books(id)        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Журнал действий пользователей (кто, что, когда)
CREATE TABLE AuditLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    user_name TEXT
);

CREATE INDEX IX_Books_Title ON Books(title);
CREATE INDEX IX_Sales_Date ON Sales(sale_date);
CREATE INDEX IX_Sales_BookDate ON Sales(book_id, sale_date);
CREATE INDEX IX_Orders_Customer ON Orders(customer_id);
CREATE INDEX IX_OrderItems_Order ON OrderItems(order_id);

-- ---------------- Представления ----------------
CREATE VIEW v_BooksFull AS
SELECT b.id, b.title, a.full_name AS author, c.name AS category,
       p.name AS publisher, b.isbn, b.price, b.stock_qty
FROM Books b
JOIN Authors a ON a.id = b.author_id
JOIN Categories c ON c.id = b.category_id
JOIN Publishers p ON p.id = b.publisher_id;

-- Все продажи: из кассы + из заказов (кроме отменённых)
CREATE VIEW v_AllSales AS
SELECT sale_date, book_id, qty, total_price AS amount
FROM Sales
UNION ALL
SELECT o.order_date, oi.book_id, oi.qty, oi.qty * oi.price
FROM OrderItems oi
JOIN Orders o ON o.id = oi.order_id
WHERE o.status <> 'Отменён';

CREATE VIEW v_SalesReport AS
SELECT date(s.sale_date) AS sale_day, b.title, a.full_name AS author,
       SUM(s.qty) AS sold_qty, SUM(s.amount) AS revenue
FROM v_AllSales s
JOIN Books b ON b.id = s.book_id
JOIN Authors a ON a.id = b.author_id
GROUP BY date(s.sale_date), b.id, b.title, a.full_name;

CREATE VIEW v_StockBalance AS
SELECT b.id, b.title, a.full_name AS author, c.name AS category,
       b.stock_qty, b.price, b.stock_qty * b.price AS stock_value
FROM Books b
JOIN Authors a ON a.id = b.author_id
JOIN Categories c ON c.id = b.category_id;

CREATE VIEW v_OrdersFull AS
SELECT o.id, o.order_date, o.customer_id, c.full_name AS customer,
       c.phone, c.address, o.status, o.total_amount
FROM Orders o
JOIN Customers c ON c.id = o.customer_id;

-- ---------------- Триггеры ----------------
-- Продажа в магазине: проверка остатка и списание
CREATE TRIGGER tr_Sales_Check
BEFORE INSERT ON Sales
BEGIN
    SELECT CASE
        WHEN (SELECT stock_qty FROM Books WHERE id = NEW.book_id) < NEW.qty
        THEN RAISE(ABORT, 'Недостаточно книг на складе')
    END;
END;

CREATE TRIGGER tr_Sales_Insert
AFTER INSERT ON Sales
BEGIN
    UPDATE Books SET stock_qty = stock_qty - NEW.qty WHERE id = NEW.book_id;
    INSERT INTO AuditLog (table_name, operation, details)
    VALUES ('Sales', 'INSERT', 'Продажа в магазине: книга ' || NEW.book_id || ', шт. ' || NEW.qty);
END;

CREATE TRIGGER tr_Sales_Delete
AFTER DELETE ON Sales
BEGIN
    UPDATE Books SET stock_qty = stock_qty + OLD.qty WHERE id = OLD.book_id;
END;

-- Заказ клиента: проверка остатка, списание, пересчёт суммы заказа
CREATE TRIGGER tr_OrderItems_Check
BEFORE INSERT ON OrderItems
BEGIN
    SELECT CASE
        WHEN (SELECT stock_qty FROM Books WHERE id = NEW.book_id) < NEW.qty
        THEN RAISE(ABORT, 'Недостаточно книг на складе')
    END;
END;

CREATE TRIGGER tr_OrderItems_Insert
AFTER INSERT ON OrderItems
BEGIN
    UPDATE Books SET stock_qty = stock_qty - NEW.qty WHERE id = NEW.book_id;
    UPDATE Orders
    SET total_amount = (SELECT SUM(qty * price) FROM OrderItems WHERE order_id = NEW.order_id)
    WHERE id = NEW.order_id;
END;

-- Отмена заказа возвращает книги на склад
CREATE TRIGGER tr_Orders_Cancel
AFTER UPDATE OF status ON Orders
WHEN NEW.status = 'Отменён' AND OLD.status <> 'Отменён'
BEGIN
    UPDATE Books
    SET stock_qty = stock_qty + (SELECT SUM(qty) FROM OrderItems
                                 WHERE order_id = NEW.id AND book_id = Books.id)
    WHERE id IN (SELECT book_id FROM OrderItems WHERE order_id = NEW.id);
END;

-- Отменённый заказ нельзя «оживить»
CREATE TRIGGER tr_Orders_NoReopen
BEFORE UPDATE OF status ON Orders
WHEN OLD.status = 'Отменён' AND NEW.status <> 'Отменён'
BEGIN
    SELECT RAISE(ABORT, 'Отменённый заказ нельзя изменить');
END;

-- Поставка увеличивает остаток и пересчитывает сумму
CREATE TRIGGER tr_SupplyItem_Insert
AFTER INSERT ON SupplyItems
BEGIN
    UPDATE Books SET stock_qty = stock_qty + NEW.qty WHERE id = NEW.book_id;
    UPDATE SupplyOrders
    SET total_amount = (SELECT COALESCE(SUM(qty * unit_price), 0) FROM SupplyItems
                        WHERE supply_order_id = NEW.supply_order_id)
    WHERE id = NEW.supply_order_id;
END;

-- Нельзя удалить книгу, по которой были продажи или заказы
CREATE TRIGGER tr_Books_BeforeDelete
BEFORE DELETE ON Books
BEGIN
    SELECT CASE
        WHEN EXISTS (SELECT 1 FROM Sales WHERE book_id = OLD.id)
          OR EXISTS (SELECT 1 FROM OrderItems WHERE book_id = OLD.id)
        THEN RAISE(ABORT, 'Нельзя удалить книгу: по ней есть продажи или заказы')
    END;
END;
