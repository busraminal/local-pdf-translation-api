using PdfTranslationApi;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

// Python FastAPI servisine istek atan HttpClient
builder.Services.AddHttpClient<ITranslationClient, TranslationClient>(client =>
{
    client.BaseAddress = new Uri("http://localhost:8000"); // Python servis URL'i
});

var app = builder.Build();

app.MapControllers();

app.Run();

