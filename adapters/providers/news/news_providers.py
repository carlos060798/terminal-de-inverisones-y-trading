"""
News providers: NewsAPI, GDELT, Reddit, StockTwits, Reuters RSS, Seeking Alpha RSS, Twitter/X
"""
import pandas as pd
import feedparser
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin, RestMixin
from adapters.registry import register

# ---------------------------------------------------------------------------
# NewsAPI — REST
# ---------------------------------------------------------------------------
@register
class NewsApiAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="newsapi", category="news",
        credential_key="NEWSAPI_KEY",
        base_url="https://newsapi.org/v2",
        rate_limit_rpm=20, ttl_seconds=900, priority="high",
    )

    def _fetch_raw(self, q: str = "finance OR economy", language: str = "en", **kwargs):
        resp = self._get("/everything", params={"q": q, "language": language, "apiKey": self._get_credential()})
        return resp.json().get("articles", [])

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        if "publishedAt" in df.columns:
            df["date"] = pd.to_datetime(df["publishedAt"])
        return DataResult(provider_id="newsapi", category="news", fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# RSS Providers (Reuters, Seeking Alpha)
# ---------------------------------------------------------------------------
@register
class ReutersRssAdapter(BaseDataAdapter):
    config = ProviderConfig(
        provider_id="reuters_rss", category="news", credential_key="",
        rate_limit_rpm=30, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, **kwargs):
        # Business/finance feed
        url = "http://feeds.reuters.com/reuters/businessNews"
        return feedparser.parse(url).entries

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        return DataResult(provider_id="reuters_rss", category="news", fetched_at="", latency_ms=0, success=True, data=df)

@register
class SeekingAlphaRssAdapter(BaseDataAdapter):
    config = ProviderConfig(
        provider_id="seeking_alpha_rss", category="news", credential_key="",
        rate_limit_rpm=30, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, **kwargs):
        url = "https://seekingalpha.com/feed.xml"
        return feedparser.parse(url).entries

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        return DataResult(provider_id="seeking_alpha_rss", category="news", fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# Reddit (praw)
# ---------------------------------------------------------------------------
@register
class RedditAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "praw"
    config = ProviderConfig(
        provider_id="reddit", category="news", credential_key="REDDIT_SECRET",
        rate_limit_rpm=60, ttl_seconds=300, priority="high",
    )

    def _fetch_raw(self, subreddit: str = "wallstreetbets", limit: int = 50, **kwargs):
        praw = self._import_lib()
        import os, streamlit as st
        client_id = st.secrets.get("REDDIT_CLIENT_ID") or os.environ.get("REDDIT_CLIENT_ID", "")
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=self._get_credential(),
            user_agent="Quantum Terminal v7"
        )
        return list(reddit.subreddit(subreddit).hot(limit=limit))

    def _normalize(self, raw) -> DataResult:
        rows = [{"title": s.title, "score": s.score, "comments": s.num_comments, "url": s.url, "created_utc": s.created_utc} for s in raw]
        df = pd.DataFrame(rows)
        if "created_utc" in df.columns:
            df["date"] = pd.to_datetime(df["created_utc"], unit="s")
        return DataResult(provider_id="reddit", category="news", fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# StockTwits & Twitter (Placeholders for complex external auth)
# ---------------------------------------------------------------------------
@register
class StocktwitsAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="stocktwits", category="news", credential_key="",
        base_url="https://api.stocktwits.com/api/2",
        rate_limit_rpm=30, ttl_seconds=300, priority="medium",
    )
    def _fetch_raw(self, ticker: str = "AAPL", **kwargs):
        resp = self._get(f"/streams/symbol/{ticker}.json")
        return resp.json().get("messages", [])
    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        return DataResult(provider_id="stocktwits", category="news", fetched_at="", latency_ms=0, success=True, data=df)
