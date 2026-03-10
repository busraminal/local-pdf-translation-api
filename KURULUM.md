# Çeviri API – Kurulum ve Çalıştırma

Bu belge, PDF ve metin çeviri servisinin kurulumu ve nasıl çalıştırılacağını anlatır.

---

## Gereksinimler

- **Python 3.9+** (3.10 veya 3.11 önerilir)
- **İnternet bağlantısı** (ilk çalıştırmada model indirilir, ~2.5 GB)
- **Yeterli disk alanı** (~3 GB)

---

## Kurulum Adımları

### 1. Proje klasörüne geç

```powershell
cd C:\Users\kullanıcı\Desktop\translate
```


### 2. Sanal ortam oluştur (önerilir)

```powershell
python -m venv .venv
```

### 3. Sanal ortamı etkinleştir

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\activate
```

Satır başında `(.venv)` görünüyorsa etkinleştirme tamamdır.

### 4. Bağımlılıkları yükle

```powershell
pip install -r requirements.txt
pip install python-multipart
```

- `requirements.txt` içinde: FastAPI, Uvicorn, Transformers, PyTorch, PyPDF.
- `python-multipart`, PDF/form yükleme için gerekli.

### 5. (İsteğe bağlı) Pip’i güncelle

```powershell
python -m pip install --upgrade pip
```

---

## Çalıştırma

### Sunucuyu başlat

Aynı klasörde ve sanal ortam açıkken **yalnızca** şu komutu yaz:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Konsolda `Uvicorn running on http://0.0.0.0:8000` ve `Application startup complete.` görünecek.
- **İlk çalıştırmada** model indirilir (birkaç dakika sürebilir). Bitene kadar bekleyin.
- Sunucuyu durdurmak için terminalde **Ctrl+C** basın.

### Tarayıcıdan erişim

- **Swagger (API test arayüzü):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Sağlık kontrolü:** [http://localhost:8000/health](http://localhost:8000/health)

Not: Adres çubuğunda **`0.0.0.0`** kullanmayın; **`localhost`** veya **`127.0.0.1`** kullanın.

---

## API Özeti

| Endpoint | Açıklama |
|----------|----------|
| `GET /health` | Servis ayakta mı kontrolü |
| `POST /translate` | Düz metin çevirisi (JSON gövde) |
| `POST /translate-pdf` | PDF yükle, içindeki metni çevir (form-data) |
| `POST /translate-stream` | Metin çevirisi (stream cevap) |

### Örnek: Metin çevirisi (`POST /translate`)

**İstek gövdesi (JSON):**

```json
{
  "text": "Merhaba dünya",
  "source_lang": "tur_Latn",
  "target_lang": "eng_Latn"
}
```

**Cevap:** `{ "translated_text": "Hello world" }` benzeri.

### Örnek: PDF çevirisi (`POST /translate-pdf`)

- **Content-Type:** `multipart/form-data`
- **Alanlar:** `file` (PDF dosyası), `source_lang`, `target_lang`
- **Cevap:** `{ "translated_text": "..." }` (PDF’ten çıkarılan ve çevrilen metin)

Dil kodları (NLLB formatı): `tur_Latn`, `eng_Latn`, `deu_Latn`, `fra_Latn` vb. Desteklenen diller için model dokümantasyonuna bakılabilir.

---

## Başka Uygulamadan Çağırma (.NET, frontend vb.)

- **Base URL:** `http://localhost:8000` (aynı makinede). Ağdan erişim için bilgisayarın IP adresi kullanılır.
- Metin çevirisi: `POST /translate` + JSON gövde.
- PDF çevirisi: `POST /translate-pdf` + multipart form (file, source_lang, target_lang).

---

## Sık Karşılaşılan Sorunlar

| Sorun | Çözüm |
|-------|--------|
| `No .NET SDKs were found` | Bu proje .NET değil, Python. `python` ve `pip` kullanın. |
| `Form data requires "python-multipart"` | `pip install python-multipart` çalıştırın. |
| `ERR_ADDRESS_INVALID` (0.0.0.0) | Tarayıcıda `http://localhost:8000` kullanın. |
| `TypeError: unsupported operand type(s) for \|` | Python 3.9 kullanıyorsanız; kodda `Optional[int]` kullanıldığından güncel `main.py` ile uyumludur. |
| Model indirme çok yavaş | İnternet hızınıza bağlı; ilk seferde 2.5 GB iner, sonra cache’den açılır. |

---

## Klasör Yapısı (özet)

```
translate/
├── app/
│   └── main.py          # FastAPI uygulaması
├── requirements.txt    # Python bağımlılıkları
├── KURULUM.md           # Bu dosya
└── .venv/               # Sanal ortam (siz oluşturursunuz)
```