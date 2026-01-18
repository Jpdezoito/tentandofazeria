from core.normalize import normalize_text, strip_accents


def test_strip_accents() -> None:
    assert strip_accents("ação") == "acao"
    assert strip_accents("José") == "Jose"


def test_normalize_text_stopwords() -> None:
    assert normalize_text("abrir o Chrome") == "chrome"
    assert normalize_text("executar   meu   jogo") == "jogo"


def test_normalize_text_keeps_extension_tokenish() -> None:
    # normalize_text keeps dots but collapses whitespace; for filenames, extension stays attached.
    assert normalize_text("abrir arquivo planilha.xlsx") == "planilha.xlsx"
