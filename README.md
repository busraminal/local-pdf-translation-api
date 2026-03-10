

```markdown
# NLLB-200 & PyMuPDF Tabanlı TR↔EN PDF Çeviri Servisi

Bu proje, **tamamen lokal çalışan**, **Python tabanlı** bir **TR↔EN çeviri servisi** sağlar.  
Amaç: PDF yüklendiğinde içeriğini Türkçe ↔ İngilizce arasında çevirmek ve mümkün olduğunca **layout’u koruyarak** bunu dış sistemler (.NET vb.) için **HTTP API** olarak sunmaktır.

---

## 🚀 Özellikler
- **Tamamen Lokal**:
  - Metin çevirisi için `facebook/nllb-200-distilled-600M`
  - TR→EN için ek olarak `Helsinki-NLP/opus-mt-tr-en`
  - PDF içerik okuma için `pypdf`
  - Layout’u yaklaşık koruyan PDF yazımı için `PyMuPDF (fitz)`
- **HTTP API (FastAPI)**:
  - `POST /translate` – Düz metin için JSON tabanlı çeviri
  - `POST /translate-pdf` – PDF metnini çıkarıp çeviren endpoint (metin döner)
  - `POST /translate-pdf-layout` – PDF’i **yaklaşık layout ile** çevirip yeni PDF döndüren endpoint
  - `POST /translate-stream` – Streaming çeviri
  - `GET /health` – Sağlık kontrolü
- **Kolay Entegrasyon**: .NET, diğer backend’ler veya frontend tarafı için sadece HTTP çağrısı yeterli.
- **Geleceğe Dönük Azure Entegrasyonu**: `azure_config.py` + `azure_document_translation.py` ile Azure Document Translation gateway’i için iskelet hazır.

---

## 🛠 Kurulum

### 1. Depoyu Klonla
```bash
git clone [https://github.com/](https://github.com/)<kullanıcı-adı>/<repo-adı>.git
cd <repo-adı>

```

### 2. Sanal Ortam (Venv)

```bash
python -m venv .venv
# Aktifleştir (Windows PowerShell):
.\.venv\Scripts\activate

```

### 3. Bağımlılıklar

```bash
pip install -r requirements.txt

```

> **Not:** İlk çalıştırmada çeviri modelleri Hugging Face’ten indirileceği için yaklaşık 3 GB disk alanı gerekir. Sonraki çalıştırmalarda modeller diskten (cache) yüklenir.

---

## 💻 Çalıştırma

### Sunucuyu Başlat

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

```

Konsolda `Uvicorn running on http://0.0.0.0:8000` satırını gördüğünüzde API hazırdır.

### Erişim

* **Swagger UI:** [http://localhost:8000/docs](https://www.google.com/search?q=http://localhost:8000/docs)
* **Sağlık Kontrolü:** [http://localhost:8000/health](https://www.google.com/search?q=http://localhost:8000/health)

---

## 📡 API Özeti

### 1. Düz Metin Çevirisi – `POST /translate`

**İstek (JSON):**

```json
{
  "text": "Merhaba dünya",
  "source_lang": "tur_Latn",
  "target_lang": "eng_Latn"
}

```

### 2. Layout Korumalı PDF Çevirisi – `POST /translate-pdf-layout`

Bu endpoint:

* PDF’i PyMuPDF ile açar.
* Metin bloklarını koordinatlarıyla çıkarır.
* Her bloğu çevirip aynı koordinatlara (`insert_textbox`) yazar.
* Yeni bir PDF dosyası döner.

---

## 🔗 .NET Entegrasyon Örneği (C#)

```csharp
using var form = new MultipartFormDataContent();
await using var fs = File.OpenRead("input.pdf");
var fileContent = new StreamContent(fs);
fileContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/pdf");

form.Add(fileContent, "file", "input.pdf");
form.Add(new StringContent("tur_Latn"), "source_lang");
form.Add(new StringContent("eng_Latn"), "target_lang");

var response = await client.PostAsync("/translate-pdf-layout", form);
if (response.IsSuccessStatusCode) {
    var outStream = await response.Content.ReadAsStreamAsync();
    using var outFile = File.Create("translated.pdf");
    await outStream.CopyToAsync(outFile);
}

```

---

## 📂 Klasör Yapısı

```text
translate/
├── app/
│   └── main.py                  # FastAPI uygulaması (endpoint'ler)
├── azure_config.py              # Azure ayarları (opsiyonel)
├── azure_document_translation.py# Azure Document Translation iskeleti
├── requirements.txt             # Python bağımlılıkları
├── dotnet/                      # Örnek .NET istemci kodları
└── .venv/                       # Sanal ortam

```

---

## ⚠️ Kısıtlar ve Notlar

* **Layout:** Çok kolonlu ve karmaşık tablolarda %100 koruma garanti edilmez.
* **Performans:** Servis ilk açılışta modelleri RAM'e yüklediği için biraz yavaş başlayabilir.
* **Gizlilik:** Varsayılan akış tamamen lokaldir; PDF içeriği dışarı gönderilmez.

```

```
