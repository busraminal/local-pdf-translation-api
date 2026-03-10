namespace PdfTranslationApi;

public record TranslationRequest(
    string Text,
    string SourceLang,
    string TargetLang
);

public record TranslationResponse(
    string TranslatedText
);

