using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using PdfTranslationApi;

namespace PdfTranslationApi;

public interface ITranslationClient
{
    Task<TranslationResponse> TranslateAsync(
        TranslationRequest request,
        CancellationToken cancellationToken = default
    );

    Task<TranslationResponse> TranslatePdfAsync(
        Stream pdfStream,
        string fileName,
        string sourceLang,
        string targetLang,
        CancellationToken cancellationToken = default
    );
}

public class TranslationClient : ITranslationClient
{
    private readonly HttpClient _httpClient;

    public TranslationClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<TranslationResponse> TranslateAsync(
        TranslationRequest request,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _httpClient.PostAsJsonAsync("/translate", request, cancellationToken);
        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<TranslationResponse>(cancellationToken: cancellationToken);
        if (result is null)
            throw new InvalidOperationException("Boş çeviri yanıtı alındı.");

        return result;
    }

    public async Task<TranslationResponse> TranslatePdfAsync(
        Stream pdfStream,
        string fileName,
        string sourceLang,
        string targetLang,
        CancellationToken cancellationToken = default
    )
    {
        using var content = new MultipartFormDataContent();

        var fileContent = new StreamContent(pdfStream);
        fileContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/pdf");

        content.Add(fileContent, "file", fileName);
        content.Add(new StringContent(sourceLang), "source_lang");
        content.Add(new StringContent(targetLang), "target_lang");

        using var response = await _httpClient.PostAsync("/translate-pdf", content, cancellationToken);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync(cancellationToken);

        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
        var result = JsonSerializer.Deserialize<TranslationResponse>(json, options);

        if (result is null)
            throw new InvalidOperationException("Boş PDF çeviri yanıtı alındı.");

        return result;
    }
}

