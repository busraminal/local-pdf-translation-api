using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

namespace PdfTranslationApi;

[ApiController]
[Route("api/[controller]")]
public class TranslationController : ControllerBase
{
    private readonly ITranslationClient _translationClient;

    public TranslationController(ITranslationClient translationClient)
    {
        _translationClient = translationClient;
    }

    /// <summary>
    /// PDF yükler ve 1–3 sayfa aralığını çevirir.
    /// direction:
    ///   - "tr-en"  -> Türkçe'den İngilizce'ye
    ///   - "en-tr"  -> İngilizce'den Türkçe'ye
    /// </summary>
    [HttpPost("translate-pdf")]
    public async Task<ActionResult<TranslationResponse>> TranslatePdf(
        IFormFile file,
        [FromForm] string direction = "tr-en",
        CancellationToken cancellationToken = default
    )
    {
        if (file == null || file.Length == 0)
            return BadRequest("PDF dosyası gereklidir.");

        if (!string.Equals(file.ContentType, "application/pdf", StringComparison.OrdinalIgnoreCase))
            return BadRequest("Yalnızca PDF dosyaları kabul edilir.");

        string sourceLang;
        string targetLang;

        direction = direction?.ToLowerInvariant() ?? string.Empty;
        switch (direction)
        {
            case "tr-en":
                sourceLang = "tur_Latn";
                targetLang = "eng_Latn";
                break;
            case "en-tr":
                sourceLang = "eng_Latn";
                targetLang = "tur_Latn";
                break;
            default:
                return BadRequest("direction sadece 'tr-en' veya 'en-tr' olabilir.");
        }

        await using var stream = file.OpenReadStream();

        var response = await _translationClient.TranslatePdfAsync(
            pdfStream: stream,
            fileName: file.FileName,
            sourceLang: sourceLang,
            targetLang: targetLang,
            cancellationToken: cancellationToken
        );

        return Ok(response);
    }
}

