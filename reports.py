"""Отчёты по продажам (магазин + заказы). Каждый отчёт возвращает (заголовки, строки)."""
import csv
import os
from datetime import datetime

import db

REPORTS_DIR = os.path.join(db.BASE_DIR, "reports")
REPORT_NAMES = ["Продажи за период", "Топ-10 книг", "Остатки на складе", "Продажи по месяцам"]


def sales_report(conn, start, end):
    headers = ["Дата", "Книга", "Автор", "Продано, шт.", "Выручка, руб."]
    rows = conn.execute(
        "SELECT sale_day, title, author, sold_qty, revenue FROM v_SalesReport "
        "WHERE sale_day BETWEEN ? AND ? ORDER BY sale_day, title", (start, end)).fetchall()
    result = [list(r) for r in rows]
    total = sum(r["revenue"] for r in rows)
    result.append(["", "ИТОГО", "", sum(r["sold_qty"] for r in rows), total])
    return headers, result


def top_books(conn):
    headers = ["Место", "Книга", "Автор", "Продано, шт.", "Выручка, руб."]
    rows = conn.execute(
        "SELECT b.title, a.full_name, SUM(s.qty) AS sold, SUM(s.amount) AS revenue "
        "FROM v_AllSales s JOIN Books b ON b.id = s.book_id JOIN Authors a ON a.id = b.author_id "
        "GROUP BY b.id, b.title, a.full_name ORDER BY sold DESC, revenue DESC LIMIT 10").fetchall()
    result = []
    place = 1
    for r in rows:
        result.append([place, r["title"], r["full_name"], r["sold"], r["revenue"]])
        place += 1
    return headers, result


def stock_report(conn):
    headers = ["Книга", "Автор", "Категория", "Остаток, шт.", "Цена", "Стоимость"]
    rows = conn.execute(
        "SELECT title, author, category, stock_qty, price, stock_value "
        "FROM v_StockBalance ORDER BY stock_qty, title").fetchall()
    result = [list(r) for r in rows]
    result.append(["ИТОГО", "", "", sum(r["stock_qty"] for r in rows), "",
                   sum(r["stock_value"] for r in rows)])
    return headers, result


def monthly_report(conn):
    headers = ["Месяц", "Продано, шт.", "Выручка, руб."]
    rows = conn.execute(
        "SELECT strftime('%Y-%m', sale_date) AS month, SUM(qty) AS qty, SUM(amount) AS revenue "
        "FROM v_AllSales GROUP BY month ORDER BY month").fetchall()
    return headers, [list(r) for r in rows]


def get_report(conn, name, start, end):
    """Выбирает нужный отчёт по названию."""
    if name == "Продажи за период":
        return sales_report(conn, start, end)
    if name == "Топ-10 книг":
        return top_books(conn)
    if name == "Остатки на складе":
        return stock_report(conn)
    return monthly_report(conn)


def save_csv(name, headers, rows):
    """Сохраняет отчёт в CSV (разделитель ; - так его правильно откроет Excel)."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORTS_DIR, name.replace(" ", "_") + "_" + stamp + ".csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)
    return path
