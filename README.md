# Python NLLB-200 Çeviri Servisi

Bu proje, `facebook/nllb-200-distilled-600M` modelini kullanan bir Python çeviri API servisidir.

- **Backend**: FastAPI
- **Model**: `facebook/nllb-200-distilled-600M` (Meta NLLB-200, Hugging Face üzerinden)
- **Entegrasyon**: .NET uygulamaları için JSON tabanlı REST API ve isteğe bağlı streaming endpoint.

## Kurulum

```bash
cd translate
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Çalıştırma

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Örnek İstek (REST)

```http
POST http://localhost:8000/translate
Content-Type: application/json

{
  "text": "Merhaba dünya",
  "source_lang": "tur_Latn",
  "target_lang": "eng_Latn"
}
```

Yanıt:

```json
{
  "translated_text": "Hello world"
}
```

## Örnek İstek (.NET HttpClient)

```csharp
var client = new HttpClient();
var body = new
{
    text = "Merhaba dünya",
    source_lang = "tur_Latn",
    target_lang = "eng_Latn"
};

var response = await client.PostAsJsonAsync("http://localhost:8000/translate", body);
response.EnsureSuccessStatusCode();

var json = await response.Content.ReadAsStringAsync();
// json -> translated_text alanını parse edin
```

