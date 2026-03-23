"""
Alternative providers: Google Trends, Wikipedia Pageviews, OpenBB
"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin, RestMixin
from adapters.registry import register

# ---------------------------------------------------------------------------
# Google Trends — pytrends
# ---------------------------------------------------------------------------
@register
class GoogleTrendsAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "pytrends.request"
    config = ProviderConfig(
        provider_id="google_trends", category="alternative", credential_key="",
        rate_limit_rpm=10, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, kw_list: list = ["recession", "bull market"], **kwargs):
        TrendReq = self._import_from("pytrends.request", "TrendReq")
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload(kw_list, timeframe="today 12-m")
        return pt.interest_over_time()

    def _normalize(self, raw) -> DataResult:
        df = raw.copy()
        if "isPartial" in df.columns:
            df.drop(columns=["isPartial"], inplace=True)
        df = df.reset_index()
        return DataResult(provider_id="google_trends", category="alternative", fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# Wikipedia Pageviews — mwviews
# ---------------------------------------------------------------------------
@register
class WikipediaPvAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "mwviews.api"
    config = ProviderConfig(
        provider_id="wikipedia_pv", category="alternative", credential_key="",
        rate_limit_rpm=30, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, pages: list = ["Apple_Inc.", "Bitcoin"], start="20240101", end="20241231", **kwargs):
        PageviewsClient = self._import_from("mwviews.api", "PageviewsClient")
        p = PageviewsClient(user_agent="QuantumTerminal")
        # .article_views uses date format YYYYMMDD
        res = p.article_views("en.wikipedia", pages, start=start, end=end)
        return res

    def _normalize(self, raw) -> DataResult:
        # dict of date -> {page: views, page2: views}
        rows = []
        for d, pv_dict in raw.items():
            r = {"date": pd.to_datetime(str(d), format="%Y%m%d", errors="coerce")}
            r.update(pv_dict)
            rows.append(r)
        df = pd.DataFrame(rows).dropna(subset=["date"])
        return DataResult(provider_id="wikipedia_pv", category="alternative", fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# OpenBB SDK (Placeholder for massive framework)
# ---------------------------------------------------------------------------
@register
class OpenbbAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "openbb"
    config = ProviderConfig(
        provider_id="openbb", category="alternative", credential_key="",
        rate_limit_rpm=30, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, symbol="AAPL", **kwargs):
        from openbb import obb
        return obb.equity.price.historical(symbol, provider="yfinance").to_df()

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(provider_id="openbb", category="alternative", fetched_at="", latency_ms=0, success=True, data=df)
