using Microsoft.Data.Sqlite;
namespace BookstoreApp;

public class BookRepository
{
    private readonly Database db;
    public BookRepository(Database db) { this.db = db; }

    private const string SelectSql =
        "SELECT id, title, isbn, price, stock_qty, author, category, publisher FROM v_BooksFull";

    // Читает одну строку результата в объект Book
    private static Book ReadBook(SqliteDataReader r) => new Book
    {
        BookId = r.GetInt32(0),
        Title = r.GetString(1),
        ISBN = r.GetString(2),
        Price = (decimal)r.GetDouble(3),   // в SQLite цена хранится как REAL
        StockQty = r.GetInt32(4),
        Author = r.GetString(5),
        Category = r.GetString(6),
        Publisher = r.GetString(7)
    };

    public List<Book> GetAll()
    {
        var books = new List<Book>();
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand(SelectSql + " ORDER BY title", conn);
        conn.Open();
        using var reader = cmd.ExecuteReader();
        while (reader.Read()) books.Add(ReadBook(reader));
        return books;
    }

    public List<Book> Search(string title)
    {
        var books = new List<Book>();
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand(
            SelectSql + " WHERE lower_ru(title) LIKE @title ORDER BY title", conn);
        // параметр защищает от SQL-инъекций
        cmd.Parameters.AddWithValue("@title", "%" + title.ToLowerInvariant() + "%");
        conn.Open();
        using var reader = cmd.ExecuteReader();
        while (reader.Read()) books.Add(ReadBook(reader));
        return books;
    }

    public void Add(string title, int authorId, int categoryId, string isbn,
        decimal price, int stockQty, int publisherId)
    {
        const string sql = "INSERT INTO Books " +
            "(title, author_id, category_id, isbn, price, stock_qty, publisher_id) " +
            "VALUES (@title, @authorId, @categoryId, @isbn, @price, @stockQty, @publisherId)";
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand(sql, conn);
        cmd.Parameters.AddWithValue("@title", title);
        cmd.Parameters.AddWithValue("@authorId", authorId);
        cmd.Parameters.AddWithValue("@categoryId", categoryId);
        cmd.Parameters.AddWithValue("@isbn", isbn);
        cmd.Parameters.AddWithValue("@price", price);
        cmd.Parameters.AddWithValue("@stockQty", stockQty);
        cmd.Parameters.AddWithValue("@publisherId", publisherId);
        conn.Open();
        cmd.ExecuteNonQuery();
    }

    public void Delete(int id)
    {
        using var conn = db.GetConnection();
        using var cmd = new SqliteCommand("DELETE FROM Books WHERE id = @id", conn);
        cmd.Parameters.AddWithValue("@id", id);
        conn.Open();
        cmd.ExecuteNonQuery();   // если по книге есть продажи, триггер вернёт ошибку
    }
}
