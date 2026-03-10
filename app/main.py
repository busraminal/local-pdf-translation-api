from typing import AsyncGenerator, Optional
import io
import argparse
import os

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from pypdf import PdfReader
import torch
import fitz  # PyMuPDF


MODEL_NAME = "facebook/nllb-200-distilled-600M"
TR_EN_MODEL_NAME = "Helsinki-NLP/opus-mt-tr-en"

# Uzun metinleri güvenli şekilde parçalara bölmek için
MAX_CHARS_PER_CHUNK = 1000

# Global model nesneleri hem API hem CLI tarafından kullanılır
tokenizer = None
model = None
tr_en_tokenizer = None
tr_en_model = None


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "tur_Latn"
    target_lang: str = "eng_Latn"


class TranslateResponse(BaseModel):
    translated_text: str


app = FastAPI(title="NLLB-200 Translation API", version="1.0.0")


@app.on_event("startup")
def load_model() -> None:
    """
    Uygulama başlarken modeli belleğe yükler.
    """
    ensure_model_loaded()


def ensure_model_loaded() -> None:
    """
    Model ve tokenizer henüz yüklenmediyse belleğe alır.
    Hem FastAPI hem de komut satırı (CLI) kullanımında ortak.
    """
    global tokenizer, model, tr_en_tokenizer, tr_en_model

    # NLLB ana modeli (diğer diller için)
    if tokenizer is None or model is None:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

    # Türkçe -> İngilizce özel modeli
    if tr_en_tokenizer is None or tr_en_model is None:
        tr_en_tokenizer = AutoTokenizer.from_pretrained(TR_EN_MODEL_NAME)
        tr_en_model = AutoModelForSeq2SeqLM.from_pretrained(TR_EN_MODEL_NAME)


def _select_model(source_lang: str, target_lang: str):
    """
    TR <-> EN için özel Marian modellerini,
    diğer tüm diller için NLLB modelini döndürür.
    """
    # Türkçe -> İngilizce (özel model)
    if source_lang in ("tur_Latn", "tur", "tr") and target_lang in ("eng_Latn", "eng", "en"):
        return tr_en_tokenizer, tr_en_model, False

    # Diğer tüm yönler için varsayılan: NLLB (forced_bos kullanarak)
    return tokenizer, model, True


def _translate_chunk(text: str, source_lang: str, target_lang: str) -> str:
    """
    Tek bir kısa metin parçasını NLLB-200 modeli ile çevirir.
    """
    # Gerekirse modeli yükle
    ensure_model_loaded()

    tok, mdl, use_forced_bos = _select_model(source_lang, target_lang)

    # NLLB için kaynak dil ayarı
    if use_forced_bos:
        tok.src_lang = source_lang

    encoded = tok(text, return_tensors="pt")
    with torch.no_grad():
        if use_forced_bos:
            generated_tokens = mdl.generate(
                **encoded,
                forced_bos_token_id=tok.convert_tokens_to_ids(target_lang),
                max_length=512,
                num_beams=2,
            )
        else:
            generated_tokens = mdl.generate(
                **encoded,
                max_length=512,
                num_beams=2,
            )

    decoded = tok.batch_decode(generated_tokens, skip_special_tokens=True)
    return decoded[0] if decoded else ""


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Verilen (uzun veya kısa) metni NLLB-200 modeli ile çevirir.
    Çok uzun metinlerde modeli zorlamamak için metni parçalara böler.
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    if len(cleaned) <= MAX_CHARS_PER_CHUNK:
        return _translate_chunk(cleaned, source_lang, target_lang)

    chunks = []
    for i in range(0, len(cleaned), MAX_CHARS_PER_CHUNK):
        piece = cleaned[i : i + MAX_CHARS_PER_CHUNK].strip()
        if not piece:
            continue
        chunks.append(_translate_chunk(piece, source_lang, target_lang))

    return "\n\n".join(chunks)


@app.post("/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest) -> TranslateResponse:
    """
    Düz metin için senkron çeviri endpoint'i.
    """
    try:
        translated = translate_text(
            request.text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
        )
    except KeyError:
        raise HTTPException(status_code=400, detail="Geçersiz dil kodu (lang code).")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return TranslateResponse(translated_text=translated)


async def streaming_generator(text: str, source_lang: str, target_lang: str) -> AsyncGenerator[bytes, None]:
    """
    Basit bir streaming mekanizması:
    - Önce tam çeviriyi üretir
    - Sonra sonucu küçük parçalar (chunk) halinde byte stream olarak gönderir
    .NET tarafı, response body'i streaming olarak okuyabilir.
    """
    translated = translate_text(text, source_lang=source_lang, target_lang=target_lang)

    # Çok basit bir chunk bölme: karakter dizisini parçalara ayır
    chunk_size = 16
    for i in range(0, len(translated), chunk_size):
        chunk = translated[i : i + chunk_size]
        if not chunk:
            continue
        yield chunk.encode("utf-8")


@app.post("/translate-stream")
async def translate_stream(request: TranslateRequest) -> StreamingResponse:
    """
    Streaming çeviri endpoint'i.

    .NET tarafı için:
    - `HttpCompletionOption.ResponseHeadersRead` ile çağırıp
    - `response.Content.ReadAsStreamAsync()` ile gelen byte stream'i parça parça okuyabilirsiniz.
    """
    gen = streaming_generator(
        request.text,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
    )
    return StreamingResponse(gen, media_type="text/plain; charset=utf-8")


@app.post("/translate-pdf", response_model=TranslateResponse)
async def translate_pdf(
    file: UploadFile = File(...),
    source_lang: str = Form("tur_Latn"),
    target_lang: str = Form("eng_Latn"),
) -> TranslateResponse:
    """
    1 ila 3 sayfalık PDF yükleyip çeviren endpoint.

    - `source_lang`: orijinal dil (örn: tur_Latn veya eng_Latn)
    - `target_lang`: hedef dil
    """
    if file.content_type not in ("application/pdf",):
        raise HTTPException(status_code=400, detail="Yalnızca PDF dosyaları kabul edilir.")

    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="PDF okunamadı.")

    num_pages = len(reader.pages)
    if num_pages == 0:
        raise HTTPException(status_code=400, detail="PDF sayfa içermiyor.")

    texts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            texts.append(page_text.strip())

    if not texts:
        raise HTTPException(status_code=400, detail="PDF içinde okunabilir metin bulunamadı.")

    full_text = "\n\n".join(texts)

    try:
        translated = translate_text(full_text, source_lang=source_lang, target_lang=target_lang)
    except KeyError:
        raise HTTPException(status_code=400, detail="Geçersiz dil kodu (lang code).")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return TranslateResponse(translated_text=translated)


def _translate_pdf_with_layout_bytes(
    pdf_bytes: bytes,
    source_lang: str,
    target_lang: str,
) -> bytes:
    """
    PyMuPDF kullanarak PDF'i blok bazlı okuyup
    yaklaşık aynı konumlara çevrilmiş metni yazar.
    Çıktı olarak yeni PDF'in bytes'ını döner.
    """
    ensure_model_loaded()

    src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    new_doc = fitz.open()

    for page in src_doc:
        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
        blocks = page.get_text("blocks")

        for block in blocks:
            # block: (x0, y0, x1, y1, text, block_no, block_type)
            if len(block) < 5:
                continue
            x0, y0, x1, y1, text_block = block[:5]
            if not text_block or not text_block.strip():
                continue

            translated = translate_text(
                text_block,
                source_lang=source_lang,
                target_lang=target_lang,
            )

            rect = fitz.Rect(x0, y0, x1, y1)
            new_page.insert_textbox(
                rect,
                translated,
                fontsize=11,
            )

    output = io.BytesIO()
    new_doc.save(output)
    new_doc.close()
    src_doc.close()
    output.seek(0)
    return output.getvalue()


@app.post("/translate-pdf-layout")
async def translate_pdf_layout(
    file: UploadFile = File(...),
    source_lang: str = Form("tur_Latn"),
    target_lang: str = Form("eng_Latn"),
):
    """
    PDF'in yaklaşık layout'unu koruyarak TR↔EN çeviren endpoint.
    Çıktı doğrudan PDF dosyası olarak döner.
    """
    if file.content_type not in ("application/pdf",):
        raise HTTPException(status_code=400, detail="Yalnızca PDF dosyaları kabul edilir.")

    try:
        content = await file.read()
        translated_bytes = _translate_pdf_with_layout_bytes(
            content,
            source_lang=source_lang,
            target_lang=target_lang,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    filename = f"translated_layout_{file.filename or 'output'}.pdf"
    return StreamingResponse(
        io.BytesIO(translated_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


def _translate_pdf_file_cli(
    pdf_path: str,
    source_lang: str = "tur_Latn",
    target_lang: str = "eng_Latn",
    max_pages: Optional[int] = None,
) -> str:
    """
    Terminalden kullanım için yardımcı fonksiyon.
    Girilen PDF dosyasını okur, metni çıkarır ve çevirir.
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF bulunamadı: {pdf_path}")

    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)

        num_pages = len(reader.pages)
        if num_pages == 0:
            raise ValueError("PDF sayfa içermiyor.")

        # max_pages None veya 0/negatif ise tüm sayfalar çevrilir
        if max_pages is not None and max_pages > 0:
            limit = min(max_pages, num_pages)
        else:
            limit = num_pages

        texts = []
        for page in reader.pages[:limit]:
            page_text = page.extract_text() or ""
            if page_text.strip():
                texts.append(page_text.strip())

        if not texts:
            raise ValueError("PDF içinde okunabilir metin bulunamadı.")

        full_text = "\n\n".join(texts)

    translated = translate_text(full_text, source_lang=source_lang, target_lang=target_lang)
    return translated


if __name__ == "__main__":
    """
    Örnek kullanım (PowerShell):

        python app/main.py .\ornek.pdf --source_lang tur_Latn --target_lang eng_Latn -o .\ceviri.txt
    """
    parser = argparse.ArgumentParser(description="NLLB-200 ile PDF çevirisi (komut satırı).")
    parser.add_argument("pdf_path", help="Çevrilecek PDF dosyasının yolu.")
    parser.add_argument(
        "--source_lang",
        default="tur_Latn",
        help="Kaynak dil kodu (varsayılan: tur_Latn).",
    )
    parser.add_argument(
        "--target_lang",
        default="eng_Latn",
        help="Hedef dil kodu (varsayılan: eng_Latn).",
    )
    parser.add_argument(
        "--max_pages",
        type=int,
        default=None,
        help="Maksimum sayfa sayısı (boş bırakılırsa tüm sayfalar).",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Çeviri çıktısının yazılacağı metin dosyası. Boş bırakılırsa ekrana yazdırılır.",
    )

    args = parser.parse_args()

    try:
        result = _translate_pdf_file_cli(
            pdf_path=args.pdf_path,
            source_lang=args.source_lang,
            target_lang=args.target_lang,
            max_pages=args.max_pages,
        )
    except Exception as exc:
        # Hata durumunda anlaşılır bir mesaj ver
        print(f"Hata: {exc}")
        raise SystemExit(1)

    if args.output:
        # Sonucu dosyaya yaz
        with open(args.output, "w", encoding="utf-8") as out_f:
            out_f.write(result)
        print(f"Çeviri '{args.output}' dosyasına yazıldı.")
    else:
        # Doğrudan terminale yaz
        print(result)
