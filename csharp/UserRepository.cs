using System.Security.Cryptography;
using System.Text;
using Microsoft.Data.Sqlite;
namespace BookstoreApp;

public class UserRepository
{
    private readonly Database db;
    public UserRepository(Database db) { this.db = db; }

    // Пароль в БД хранится как "соль$sha256(соль + пароль)" - так же, как в Python-приложении
    private static bool CheckPassword(string password, string stored)
    {
        var parts = stored.Split('$');
        if (parts.Length != 2) return false;
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(parts[0] + password));
        return Convert.ToHexString(bytes).ToLowerInvariant() == parts[1];
    }

    // Сначала ищем среди сотрудников, потом среди клиентов (читателей)
    public User? Login(string login, string password)
    {
        using var conn = db.GetConnection();
        conn.Open();

        using (var cmd = new SqliteCommand(
            "SELECT id, full_name, role, password_hash FROM Employees WHERE login = @l", conn))
        {
            cmd.Parameters.AddWithValue("@l", login);
            using var r = cmd.ExecuteReader();
            if (r.Read() && !r.IsDBNull(3) && CheckPassword(password, r.GetString(3)))
                return new User(r.GetString(1), r.GetString(2), r.GetInt32(0), null);
        }

        using (var cmd = new SqliteCommand(
            "SELECT id, full_name, password_hash FROM Customers WHERE login = @l", conn))
        {
            cmd.Parameters.AddWithValue("@l", login);
            using var r = cmd.ExecuteReader();
            if (r.Read() && !r.IsDBNull(2) && CheckPassword(password, r.GetString(2)))
                return new User(r.GetString(1), "reader", null, r.GetInt32(0));
        }

        return null;
    }
}
