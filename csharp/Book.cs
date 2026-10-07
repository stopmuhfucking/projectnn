namespace BookstoreApp;

public class Book
{
    public int BookId { get; set; }
    public string Title { get; set; } = "";
    public string ISBN { get; set; } = "";
    public decimal Price { get; set; }
    public int StockQty { get; set; }
    public string Author { get; set; } = "";
    public string Category { get; set; } = "";
    public string Publisher { get; set; } = "";
}

// Вошедший пользователь. Role: "reader", "manager" или "owner".
public record User(string Name, string Role, int? EmployeeId, int? CustomerId);
