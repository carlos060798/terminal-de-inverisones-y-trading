"""
Commodity providers: EIA, USDA, World Bank Commodities, CME (CSV)
"""
import pandas as pd
from io import BytesIO
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin, RestMixin, CsvMixin
from adapters.registry import register

# ---------------------------------------------------------------------------
# EIA (US Energy Information Administration) — eia-python or REST
# ---------------------------------------------------------------------------
@register
class EiaAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="eia", category="commodities",
        credential_key="EIA_API_KEY",
        base_url="https://api.eia.gov/v2",
        rate_limit_rpm=30, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, route: str = "petroleum/pri/spt/data", frequency: str = "daily", **kwargs):
        # https://api.eia.gov/v2/petroleum/pri/spt/data/?frequency=daily&data[0]=value
        params = {
            "api_key": self._get_credential(),
            "frequency": frequency,
            "data[0]": "value"
        }
        resp = self._get(f"/{route}", params=params)
        return resp.json().get("response", {}).get("data", [])

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        if "period" in df.columns:
            df["date"] = pd.to_datetime(df["period"], errors="coerce")
        return DataResult(provider_id="eia", category="commodities",
                          fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# USDA (US Dept of Agriculture) — REST
# ---------------------------------------------------------------------------
@register
class UsdaAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="usda", category="commodities",
        credential_key="USDA_KEY",
        base_url="https://quickstats.nass.usda.gov/api",
        rate_limit_rpm=10, ttl_seconds=86400, priority="batch",
    )

    def _fetch_raw(self, commodity: str = "CORN", **kwargs):
        params = {
            "key": self._get_credential(),
            "commodity_desc": commodity.upper(),
            "format": "JSON"
        }
        resp = self._get("/api_GET", params=params)
        return resp.json().get("data", [])

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        return DataResult(provider_id="usda", category="commodities",
                          fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# World Bank Commodities (Pink Sheet) — REST/CSV
# ---------------------------------------------------------------------------
@register
class WbCommoditiesAdapter(CsvMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="wb_commodities", category="commodities",
        credential_key="",
        rate_limit_rpm=10, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, **kwargs):
        # Pink sheet monthly data CSV
        url = "https://thedocs.worldbank.org/en/doc/5d1033888d6e38eb41328bbd9120562e-0350012021/related/CMO-Historical-Data-Monthly.xlsx"
        resp = self._get_csv(url)  # actually excel, so we read with pandas
        return pd.read_excel(BytesIO(resp.content), sheet_name="Monthly Prices", skiprows=6)

    def _normalize(self, raw: pd.DataFrame) -> DataResult:
        df = raw.copy()
        df.rename(columns={df.columns[0]: "date"}, inplace=True)
        return DataResult(provider_id="wb_commodities", category="commodities",
                          fetched_at="", latency_ms=0, success=True, data=df)

# ---------------------------------------------------------------------------
# CME Group (Via yfinance/futures)
# ---------------------------------------------------------------------------
@register
class CmeAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "yfinance"
    config = ProviderConfig(
        provider_id="cme", category="commodities",
        credential_key="",
        rate_limit_rpm=60, ttl_seconds=300, priority="high",
    )

    def _fetch_raw(self, ticker: str = "CL=F", **kwargs):
        # CL=F (Crude Oil), GC=F (Gold), ZC=F (Corn)
        yf = self._import_lib()
        t = yf.Ticker(ticker)
        return t.history(period="1y")

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(provider_id="cme", category="commodities",
                          fetched_at="", latency_ms=0, success=True, data=df)
