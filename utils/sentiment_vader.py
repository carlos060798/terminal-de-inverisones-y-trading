"""
Sentiment Analysis Engine using VADER + RSS feeds.
Fetches financial news headlines and scores them for market sentiment.
"""
import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from datetime import datetime

_sia = None

def _get_sia():
    global _sia
    if _sia is None:
        import nltk
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
        _sia = SentimentIntensityAnalyzer()
    return _sia


# Financial RSS feeds (free, no API key required)
RSS_FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssurl",
    "Yahoo Markets": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "Reuters Business": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "Investing.com": "https://www.investing.com/rss/news.rss",
}


def fetch_headlines(max_per_feed: int = 10) -> list:
    """
    Fetch recent financial headlines from multiple RSS sources.
    Returns list of dicts: [{'title': str, 'source': str, 'published': str, 'link': str}]
    """
    headlines = []

    for source_name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                if title and len(title) > 10:
                    published = entry.get("published", entry.get("updated", ""))
                    headlines.append({
                        "title": title,
                        "source": source_name,
                        "published": published[:25] if published else "",
                        "link": entry.get("link", ""),
                    })
        except Exception:
            continue

    return headlines


def analyze_headlines(headlines: list) -> list:
    """
    Score each headline using VADER.
    Returns list with added 'compound', 'label' fields.
    """
    sia = _get_sia()
    results = []

    for h in headlines:
        scores = sia.polarity_scores(h["title"])
        compound = scores["compound"]

        if compound >= 0.15:
            label = "Bullish"
        elif compound <= -0.15:
            label = "Bearish"
        else:
            label = "Neutral"

        results.append({
            **h,
            "compound": round(compound, 3),
            "positive": round(scores["pos"], 3),
            "negative": round(scores["neg"], 3),
            "label": label,
        })

    return results


def get_sentiment_pulse() -> dict:
    """
    Main function: fetch headlines, analyze, and return aggregate sentiment.
    Returns dict with:
        - score: float (-100 to +100)
        - label: str (Extreme Fear / Fear / Neutral / Greed / Extreme Greed)
        - bullish_count, bearish_count, neutral_count
        - headlines: list of analyzed headlines
        - timestamp: str
    """
    headlines = fetch_headlines(max_per_feed=8)

    if not headlines:
        return {
            "score": 0, "label": "Sin datos", "bullish_count": 0,
            "bearish_count": 0, "neutral_count": 0, "headlines": [],
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }

    analyzed = analyze_headlines(headlines)

    # Aggregate: weighted average of compound scores -> -100 to +100 scale
    compounds = [h["compound"] for h in analyzed]
    avg_compound = sum(compounds) / len(compounds) if compounds else 0
    score = avg_compound * 100  # Scale to -100 / +100

    bullish = sum(1 for h in analyzed if h["label"] == "Bullish")
    bearish = sum(1 for h in analyzed if h["label"] == "Bearish")
    neutral = sum(1 for h in analyzed if h["label"] == "Neutral")

    # Market condition label
    if score >= 40:
        label = "Extreme Greed 🤑"
    elif score >= 15:
        label = "Greed 📈"
    elif score <= -40:
        label = "Extreme Fear 😱"
    elif score <= -15:
        label = "Fear 📉"
    else:
        label = "Neutral ⚖️"

    return {
        "score": round(score, 1),
        "label": label,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "total": len(analyzed),
        "headlines": sorted(analyzed, key=lambda x: abs(x["compound"]), reverse=True),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
