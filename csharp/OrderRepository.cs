using Microsoft.Data.Sqlite;
namespace BookstoreApp;

public class OrderRepository
{
    private readonly Database db;
    public OrderRepository(Database db) { this.db = db; }

    // Создаёт заказ и его состав в ОДНОЙ транзакции: если книги не хватает,
    // триггер вернёт ошибку и откатится весь заказ. Сумму и остаток считают триггеры.
    public int CreateOrder(int customerId, List<(int BookId, int Qty)> items)
    {
        if (items.Count == 0) throw new InvalidOperationException("Корзина пуста");

        using var conn = db.GetConnection();
        conn.Open();
        using var tx = conn.BeginTransaction();
        try
        {
            int orderId;
            using (var cmd = conn.CreateCommand())
            {
                cmd.Transaction = tx;
                cmd.CommandText = "INSERT INTO Orders (customer_id) VALUES (@c); SELECT last_insert_rowid();";
                cmd.Parameters.AddWithValue("@c", customerId);
                orderId = Convert.ToInt32(cmd.ExecuteScalar());
            }

            foreach (var item in items)
            {
                using var cmd = conn.CreateCommand();
                cmd.Transaction = tx;
                // цена берётся из каталога на момент заказа
                cmd.CommandText = "INSERT INTO OrderItems (order_id, book_id, qty, price) " +
                                  "VALUES (@o, @b, @q, (SELECT price FROM Books WHERE id = @b))";
                cmd.Parameters.AddWithValue("@o", orderId);
                cmd.Parameters.AddWithValue("@b", item.BookId);
                cmd.Parameters.AddWithValue("@q", item.Qty);
                cmd.ExecuteNonQuery();
            }

            tx.Commit();
            return orderId;
        }
        catch
        {
            tx.Rollback();
            throw;
        }
    }

    // customerId = null - показать все заказы (менеджер, владелец)
    public void ShowOrders(int? customerId)
    {
        var sql = "SELECT id, order_date, customer, status, total_amount FROM v_OrdersFull";
        if (customerId != null) sql += " WHERE customer_id = @c";
        sql += " ORDER BY id DESC";

        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand(sql, conn);
        if (customerId != null) cmd.Parameters.AddWithValue("@c", customerId);
        conn.Open();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
            Console.WriteLine($"Заказ №{reader.GetInt32(0)} | {reader.GetString(1)} | {reader.GetString(2)} | {reader.GetString(3)} | {reader.GetDouble(4):F2} руб.");
    }

    public void ShowItems(int orderId)
    {
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand(
            "SELECT b.title, oi.qty, oi.price FROM OrderItems oi " +
            "JOIN Books b ON b.id = oi.book_id WHERE oi.order_id = @o", conn);
        cmd.Parameters.AddWithValue("@o", orderId);
        conn.Open();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
            Console.WriteLine($"   {reader.GetString(0)} - {reader.GetInt32(1)} шт. x {reader.GetDouble(2):F2} руб.");
    }

    public void SetStatus(int orderId, string status)
    {
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand("UPDATE Orders SET status = @s WHERE id = @o", conn);
        cmd.Parameters.AddWithValue("@s", status);
        cmd.Parameters.AddWithValue("@o", orderId);
        conn.Open();
        cmd.ExecuteNonQuery();   // недопустимый статус отклонит CHECK в таблице
    }
}
