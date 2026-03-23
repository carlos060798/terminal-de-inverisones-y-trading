"""
Volatility providers: CFTC COT, Deribit, Nasdaq Options, Calc VIX
"""
import pandas as pd
from io import BytesIO
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import RestMixin, CsvMixin, LibraryMixin
from adapters.registry import register

# ---------------------------------------------------------------------------
# CFTC COT (Commitments of Traders) — CSV/ZIP
# ---------------------------------------------------------------------------
@register
class CftcCotAdapter(CsvMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="cftc_cot", category="volatility",
        credential_key="", rate_limit_rpm=10, ttl_seconds=86400, priority="batch",
    )

    def _fetch_raw(self, **kwargs):
        # Weekly data in zip
        url = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_2024.zip"
        # We assume the user has a more robust logic, but we provide the baseline:
        resp = self._get_csv(url)
        return pd.read_csv(BytesIO(resp.content), compression='zip')

    def _normalize(self, raw: pd.DataFrame) -> DataResult:
        df = raw.copy()
        if "Report_Date_as_MM_DD_YYYY" in df.columns:
            df["date"] = pd.to_datetime(df["Report_Date_as_MM_DD_YYYY"])
        return DataResult(provider_id="cftc_cot", category="volatility", fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# Deribit (Crypto Options/Volatility) — REST
# ---------------------------------------------------------------------------
@register
class DeribitAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="deribit", category="volatility", credential_key="",
        base_url="https://www.deribit.com/api/v2/public",
        rate_limit_rpm=60, ttl_seconds=300, priority="realtime",
    )

    def _fetch_raw(self, currency: str = "BTC", **kwargs):
        resp = self._get("/get_historical_volatility", params={"currency": currency})
        return resp.json().get("result", [])

    def _normalize(self, raw) -> DataResult:
        rows = [{"date": pd.to_datetime(d[0], unit="ms"), "volatility": d[1]} for d in raw]
        df = pd.DataFrame(rows)
        return DataResult(provider_id="deribit", category="volatility", fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# Nasdaq Options (Placeholder using yfinance or Nasdaq Data Link)
# ---------------------------------------------------------------------------
@register
class NasdaqOptionsAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "nasdaqdatalink"
    config = ProviderConfig(
        provider_id="nasdaq_options", category="volatility", credential_key="NASDAQ_DATA_LINK_KEY",
        rate_limit_rpm=10, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, ticker: str = "AAPL", **kwargs):
        ndl = self._import_lib()
        ndl.ApiConfig.api_key = self._get_credential()
        return ndl.get(f"WIKI/{ticker}")  # WIKI placeholder
    
    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index() if hasattr(raw, "reset_index") else pd.DataFrame(raw)
        return DataResult(provider_id="nasdaq_options", category="volatility", fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# Calc VIX (Local heuristic calculation based on SPY options)
# ---------------------------------------------------------------------------
@register
class CalcVixAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "yfinance"
    config = ProviderConfig(
        provider_id="calc_vix", category="volatility", credential_key="",
        rate_limit_rpm=30, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, **kwargs):
        yf = self._import_lib()
        t = yf.Ticker("SPY")
        dates = t.options[:1]
        if not dates: return 0
        puts = t.option_chain(dates[0]).puts
        calls = t.option_chain(dates[0]).calls
        total_vol = puts["volume"].sum() + calls["volume"].sum()
        # simplified local calculation based on option volume as a proxy
        return total_vol / 1000

    def _normalize(self, raw) -> DataResult:
        return DataResult(provider_id="calc_vix", category="volatility", fetched_at="", latency_ms=0, success=True, data={"calculated_vix_proxy": raw})
