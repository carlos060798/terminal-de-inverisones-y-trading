"""
Remaining stock providers:
  marketstack, quandl, stooq, iex_cloud, intrinio, simfin, finviz
All follow the same BaseDataAdapter + Mixin pattern.
"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin, RestMixin
from adapters.registry import register


# ---------------------------------------------------------------------------
# Marketstack
# ---------------------------------------------------------------------------
@register
class MarketstackAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="marketstack", category="stocks",
        credential_key="MARKET_STOCK_API_KEY",
        base_url="http://api.marketstack.com/v1",
        rate_limit_rpm=10, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, ticker: str = "AAPL", limit: int = 100, **kwargs):
        resp = self._get("/eod", params={"access_key": self._get_credential(),
                                          "symbols": ticker, "limit": limit})
        return resp.json().get("data", [])

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], utc=True)
        return DataResult(provider_id="marketstack", category="stocks",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# Quandl / NASDAQ Data Link
# ---------------------------------------------------------------------------
@register
class QuandlAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "nasdaqdatalink"
    config = ProviderConfig(
        provider_id="quandl", category="stocks",
        credential_key="NASDAQ_DATA_LINK_KEY",
        rate_limit_rpm=20, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, dataset: str = "WIKI/AAPL", **kwargs):
        ndl = self._import_lib()
        ndl.ApiConfig.api_key = self._get_credential()
        return ndl.get(dataset)

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index() if hasattr(raw, "reset_index") else pd.DataFrame(raw)
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
        return DataResult(provider_id="quandl", category="stocks",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# Stooq — pandas_datareader
# ---------------------------------------------------------------------------
@register
class StooqAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "pandas_datareader.data"
    config = ProviderConfig(
        provider_id="stooq", category="stocks",
        credential_key="",
        rate_limit_rpm=20, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, ticker: str = "AAPL.US", **kwargs):
        web = self._import_lib()
        return web.DataReader(ticker, "stooq")

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"], utc=True)
        return DataResult(provider_id="stooq", category="stocks",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# IEX Cloud — pyEX
# ---------------------------------------------------------------------------
@register
class IexCloudAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "pyEX"
    config = ProviderConfig(
        provider_id="iex_cloud", category="stocks",
        credential_key="IEX_TOKEN",
        rate_limit_rpm=100, ttl_seconds=60, priority="high",
    )

    def _fetch_raw(self, ticker: str = "AAPL", **kwargs):
        pyEX = self._import_lib()
        c = pyEX.Client(api_token=self._get_credential())
        return c.chartDF(ticker)

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index() if hasattr(raw, "reset_index") else pd.DataFrame(raw)
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(provider_id="iex_cloud", category="stocks",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# Intrinio — intrinio-sdk
# ---------------------------------------------------------------------------
@register
class IntrinioAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "intrinio_sdk"
    config = ProviderConfig(
        provider_id="intrinio", category="stocks",
        credential_key="INTRINIO_KEY",
        rate_limit_rpm=60, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, ticker: str = "AAPL", **kwargs):
        intrinio = self._import_lib()
        intrinio.ApiClient().configuration.api_key["api_key"] = self._get_credential()
        api = intrinio.SecurityApi()
        resp = api.get_security_stock_prices(ticker)
        return resp.stock_prices

    def _normalize(self, raw) -> DataResult:
        rows = [p.to_dict() if hasattr(p, "to_dict") else p for p in (raw or [])]
        df = pd.DataFrame(rows)
        return DataResult(provider_id="intrinio", category="stocks",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# SimFin — simfin
# ---------------------------------------------------------------------------
@register
class SimfinAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "simfin"
    config = ProviderConfig(
        provider_id="simfin", category="stocks",
        credential_key="SIMFIN_KEY",
        rate_limit_rpm=10, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, dataset: str = "income", variant: str = "annual",
                   market: str = "us", **kwargs):
        sf = self._import_lib()
        sf.set_api_key(self._get_credential())
        return sf.load(dataset=dataset, variant=variant, market=market)

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index() if hasattr(raw, "reset_index") else pd.DataFrame(raw)
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
        return DataResult(provider_id="simfin", category="stocks",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# Finviz — finvizfinance (migrated from data_sources.py)
# ---------------------------------------------------------------------------
@register
class FinvizAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "finvizfinance.quote"
    config = ProviderConfig(
        provider_id="finviz", category="stocks",
        credential_key="",
        rate_limit_rpm=20, ttl_seconds=600, priority="medium",
    )

    def _fetch_raw(self, ticker: str = "AAPL", **kwargs):
        FinvizFinance = self._import_from("finvizfinance.quote", "finvizfinance")
        stock = FinvizFinance(ticker)
        return stock.ticker_inside_trader()

    def _normalize(self, raw) -> DataResult:
        df = raw if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw or [])
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
        return DataResult(provider_id="finviz", category="stocks",
                          fetched_at="", latency_ms=0, success=True, data=df)
