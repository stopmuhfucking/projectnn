using BookstoreApp;

// Ищем bookstore.db в текущей и родительских папках (там же лежит Python-приложение)
var dbPath = args.Length > 0 ? args[0] : FindDb();
if (dbPath == null)
{
    Console.WriteLine("Файл bookstore.db не найден. Создайте его: python db.py");
    return;
}

var db = new Database(dbPath);
var books = new BookRepository(db);
var sales = new SaleRepository(db);
var orders = new OrderRepository(db);
var users = new UserRepository(db);

// ---- Вход (3 попытки) ----
User? user = null;
for (int attempt = 1; attempt <= 3 && user == null; attempt++)
{
    Console.Write("Логин: ");
    var login = Console.ReadLine() ?? "";
    Console.Write("Пароль: ");
    var password = Console.ReadLine() ?? "";
    user = users.Login(login, password);
    if (user == null) Console.WriteLine("Неверный логин или пароль.");
}
if (user == null)
{
    Console.WriteLine("Вход не выполнен.");
    return;
}
Console.WriteLine($"Вы вошли как {user.Name} ({user.Role})");

bool isReader = user.Role == "reader";
bool isStaff = user.Role == "manager" || user.Role == "owner";
bool isOwner = user.Role == "owner";

// ---- Меню (пункты зависят от роли) ----
while (true)
{
    Console.WriteLine("\nКНИЖНЫЙ МАГАЗИН");
    Console.WriteLine("1 - Показать книги");
    Console.WriteLine("2 - Поиск книги");
    if (isReader) Console.WriteLine("3 - Оформить заказ\n4 - Мои заказы");
    if (isStaff) Console.WriteLine("5 - Добавить книгу\n6 - Все заказы\n7 - Сменить статус заказа\n8 - Продажа в магазине\n9 - Продажи по дням\n10 - Топ-10 книг");
    if (isOwner) Console.WriteLine("11 - Удалить книгу");
    Console.WriteLine("0 - Выход");
    Console.Write("Выберите пункт: ");
    var choice = Console.ReadLine();

    try
    {
        switch (choice)
        {
            case "1":
                foreach (var b in books.GetAll()) PrintBook(b);
                break;
            case "2":
                Console.Write("Название: ");
                foreach (var b in books.Search(Console.ReadLine() ?? "")) PrintBook(b);
                break;
            case "3" when isReader:
                var items = new List<(int BookId, int Qty)>();
                while (true)
                {
                    Console.Write("ID книги (пусто - закончить): ");
                    var idText = Console.ReadLine();
                    if (string.IsNullOrWhiteSpace(idText)) break;
                    Console.Write("Количество: ");
                    items.Add((int.Parse(idText), int.Parse(Console.ReadLine()!)));
                }
                var orderId = orders.CreateOrder(user.CustomerId!.Value, items);
                Console.WriteLine($"Заказ №{orderId} оформлен.");
                break;
            case "4" when isReader:
                orders.ShowOrders(user.CustomerId);
                break;
            case "5" when isStaff:
                Console.Write("Название: "); var title = Console.ReadLine() ?? "";
                Console.Write("ID автора: "); var authorId = int.Parse(Console.ReadLine()!);
                Console.Write("ID категории: "); var categoryId = int.Parse(Console.ReadLine()!);
                Console.Write("ISBN (13 цифр): "); var isbn = Console.ReadLine() ?? "";
                Console.Write("Цена: "); var price = decimal.Parse(Console.ReadLine()!);
                Console.Write("Количество: "); var stock = int.Parse(Console.ReadLine()!);
                Console.Write("ID издательства: "); var publisherId = int.Parse(Console.ReadLine()!);
                books.Add(title, authorId, categoryId, isbn, price, stock, publisherId);
                Console.WriteLine("Книга добавлена.");
                break;
            case "6" when isStaff:
                orders.ShowOrders(null);
                break;
            case "7" when isStaff:
                Console.Write("Номер заказа: "); var statusOrderId = int.Parse(Console.ReadLine()!);
                Console.Write("Новый статус (Новый, Собран, Отправлен, Доставлен, Отменён): ");
                orders.SetStatus(statusOrderId, Console.ReadLine() ?? "");
                Console.WriteLine("Статус изменён.");
                break;
            case "8" when isStaff:
                Console.Write("ID книги: "); var saleBookId = int.Parse(Console.ReadLine()!);
                Console.Write("Количество: "); var saleQty = int.Parse(Console.ReadLine()!);
                sales.AddSale(saleBookId, null, saleQty, user.EmployeeId!.Value);
                Console.WriteLine("Продажа оформлена.");
                break;
            case "9" when isStaff:
                sales.ShowSales();
                break;
            case "10" when isStaff:
                sales.ShowTopBooks();
                break;
            case "11" when isOwner:
                Console.Write("ID книги: ");
                books.Delete(int.Parse(Console.ReadLine()!));
                Console.WriteLine("Книга удалена.");
                break;
            case "0":
                return;
            default:
                Console.WriteLine("Неверный пункт или нет прав.");
                break;
        }
    }
    catch (Exception ex)
    {
        Console.WriteLine("Ошибка: " + ex.Message);
    }
}

static void PrintBook(Book b) =>
    Console.WriteLine($"{b.BookId}. {b.Title} | {b.Author} | {b.Price:F2} руб. | остаток {b.StockQty}");

static string? FindDb()
{
    var dir = new DirectoryInfo(AppContext.BaseDirectory);
    while (dir != null)
    {
        var candidate = Path.Combine(dir.FullName, "bookstore.db");
        if (File.Exists(candidate)) return candidate;
        dir = dir.Parent;
    }
    return null;
}
