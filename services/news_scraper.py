"""services/news_scraper.py - RSS Feed Parser for financial news."""
import feedparser
from datetime import datetime, timezone, timedelta
import re

FEEDS = {
    "reuters": "https://feeds.reuters.com/reuters/businessNews",
    "yahoo_fin": "https://finance.yahoo.com/news/rssindex",
    "seeking_alpha": "https://seekingalpha.com/feed.xml",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories",
    "wsj": "https://feeds.a.wsj.com/rss/RSSMarketsMain.xml",
}

KNOWN_TICKERS = {"AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "JPM", "SPY", "QQQ"}

class NewsItem:
    def __init__(self, title, summary, link, source, published, tickers=None):
        self.title = title
        self.summary = summary
        self.link = link
        self.source = source
        self.published = published
        self.tickers = tickers or []

def extract_tickers(text: str, known: set = KNOWN_TICKERS) -> list[str]:
    candidates = re.findall(r'\$([A-Z]{1,5})|(?<!\w)([A-Z]{2,5})(?!\w)', text)
    found = {a or b for a, b in candidates}
    return sorted(list(found & known))

def fetch_feed(name: str, url: str) -> list[NewsItem]:
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in getattr(feed, 'entries', []):
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                published = datetime.now(timezone.utc)
            items.append(NewsItem(
                title=entry.get("title", ""),
                summary=entry.get("summary", ""),
                link=entry.get("link", ""),
                source=name,
                published=published
            ))
        return items
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return []

def news_for_ticker(ticker: str, hours_back: int = 48) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    results = []
    
    for name, url in FEEDS.items():
        for item in fetch_feed(name, url):
            if item.published < cutoff:
                continue
            full_text = f"{item.title} {item.summary}"
            item.tickers = extract_tickers(full_text)
            if ticker in item.tickers or ticker in full_text:
                results.append(item)
                
    return sorted(results, key=lambda x: x.published, reverse=True)
