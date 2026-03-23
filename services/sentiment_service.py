"""Sentiment Service — FinBERT-based financial sentiment analysis."""


def analyze_headlines(headlines):
    """Analyze financial sentiment for a list of headlines using FinBERT via HF.

    Parameters
    ----------
    headlines : list[str]
        Up to 10 headline strings to classify.

    Returns
    -------
    list[dict]
        Each dict has keys ``label`` (str) and ``score`` (float).
    """
    try:
        from backends import hf_backend
        return hf_backend.sentiment(headlines)
    except Exception:
        return []


def classify_news(text):
    """Classify a single text string for financial sentiment.

    Returns
    -------
    dict
        ``{"label": str, "score": float}``
    """
    results = analyze_headlines([text])
    return results[0] if results else {"label": "neutral", "score": 0.5}
