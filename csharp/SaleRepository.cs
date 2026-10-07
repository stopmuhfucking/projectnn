using Microsoft.Data.Sqlite;
namespace BookstoreApp;

public class SaleRepository
{
    private readonly Database db;
    public SaleRepository(Database db) { this.db = db; }

    // Продажа в магазине. Сумму считает сам SQL, остаток списывает триггер.
    public void AddSale(int bookId, int? customerId, int qty, int employeeId)
    {
        const string sql =
            "INSERT INTO Sales (book_id, customer_id, qty, total_price, employee_id) " +
            "VALUES (@bookId, @customerId, @qty, (SELECT price FROM Books WHERE id = @bookId) * @qty, @employeeId)";
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand(sql, conn);
        cmd.Parameters.AddWithValue("@bookId", bookId);
        cmd.Parameters.AddWithValue("@customerId", (object?)customerId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@qty", qty);
        cmd.Parameters.AddWithValue("@employeeId", employeeId);
        conn.Open();
        cmd.ExecuteNonQuery();
    }

    public void ShowSales()
    {
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand(
            "SELECT sale_day, title, sold_qty, revenue FROM v_SalesReport ORDER BY sale_day DESC", conn);
        conn.Open();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
            Console.WriteLine($"{reader.GetString(0)} | {reader.GetString(1)} | {reader.GetInt32(2)} шт. | {reader.GetDouble(3):F2} руб.");
    }

    public void ShowTopBooks()
    {
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand(
            "SELECT b.title, SUM(s.qty) FROM v_AllSales s JOIN Books b ON b.id = s.book_id " +
            "GROUP BY b.id, b.title ORDER BY SUM(s.qty) DESC LIMIT 10", conn);
        conn.Open();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
            Console.WriteLine($"{reader.GetString(0)} - {reader.GetInt32(1)} шт.");
    }
}
