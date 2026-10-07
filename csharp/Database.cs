using Microsoft.Data.Sqlite;
namespace BookstoreApp;

public class Database
{
    private readonly string connectionString;

    public Database(string filePath)
    {
        // Foreign Keys=True включает внешние ключи (в SQLite они по умолчанию выключены)
        connectionString = $"Data Source={filePath};Foreign Keys=True";
    }

    public SqliteConnection GetConnection()
    {
        var conn = new SqliteConnection(connectionString);
        // LIKE в SQLite не различает регистр только у латиницы, поэтому добавляем свою функцию
        conn.CreateFunction("lower_ru", (string? s) => s?.ToLowerInvariant());
        return conn;
    }
}
