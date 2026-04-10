"""services/local_sentiment.py - FinBERT offline sentiment analysis."""
import os

_pipe = None

def get_sentiment(texts: list[str]) -> list[dict]:
    global _pipe
    try:
        if _pipe is None:
            from transformers import pipeline
            import torch
            device = -1 # Always use CPU
            _pipe = pipeline("text-classification", model="ProsusAI/finbert", device=device)
        return _pipe(texts, truncation=True, max_length=512)
    except Exception as e:
        print(f"Error loading FinBERT: {e}")
        return [{"label": "neutral", "score": 1.0} for _ in texts]

def analyze_ticker_sentiment(ticker: str, hours_back: int = 48) -> dict:
    from services.news_scraper import news_for_ticker
    
    news = news_for_ticker(ticker, hours_back=hours_back)
    texts = [f"{n.title}. {n.summary[:200]}" for n in news]

    if not texts:
        return {"ticker": ticker, "score": 0.0, "count": 0, "headlines": []}

    results = get_sentiment(texts)
    label_map = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}

    scores = [label_map.get(r.get("label", "neutral").lower(), 0.0) * r.get("score", 0.0) for r in results]
    avg = sum(scores) / len(scores) if scores else 0.0

    return {
        "ticker": ticker,
        "score": round(avg, 4),
        "count": len(news),
        "positive": sum(1 for r in results if r.get("label", "neutral").lower() == "positive"),
        "negative": sum(1 for r in results if r.get("label", "neutral").lower() == "negative"),
        "neutral": sum(1 for r in results if r.get("label", "neutral").lower() == "neutral"),
        "headlines": [n.title for n in news[:5]],
    }

def normalize_sentiment(score: float) -> float:
    """Convierte -1.0/+1.0 -> 0/100"""
    return round((score + 1.0) / 2.0 * 100, 2)
