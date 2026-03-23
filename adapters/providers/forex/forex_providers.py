"""
Forex providers: ECB Forex, Open Exchange Rates, Fixer.io, CurrencyFreaks, OANDA
"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin, RestMixin
from adapters.registry import register


# ---------------------------------------------------------------------------
# ECB Exchange Rates — sdmx1
# ---------------------------------------------------------------------------
@register
class EcbForexAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "sdmx"
    config = ProviderConfig(
        provider_id="ecb_forex", category="forex",
        credential_key="",
        rate_limit_rpm=20, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, key: str = "D.USD.EUR.SP00.A", **kwargs):
        sdmx = self._import_lib()
        ecb = sdmx.Request("ECB")
        resp = ecb.data("EXR", key=key)
        return sdmx.to_pandas(resp)

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index() if hasattr(raw, "reset_index") else pd.DataFrame({"value": raw})
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(provider_id="ecb_forex", category="forex",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# Open Exchange Rates — REST
# ---------------------------------------------------------------------------
@register
class OpenExchangeRatesAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="open_exchange", category="forex",
        credential_key="OPEN_EXCHANGE_KEY",
        base_url="https://openexchangerates.org/api",
        rate_limit_rpm=10, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, base: str = "USD", **kwargs):
        resp = self._get("/latest.json", params={"app_id": self._get_credential(), "base": base})
        return resp.json()

    def _normalize(self, raw) -> DataResult:
        rates = raw.get("rates", {})
        df = pd.DataFrame([{"currency": k, "rate": v} for k, v in rates.items()])
        return DataResult(provider_id="open_exchange", category="forex",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# Fixer.io — fixerio library
# ---------------------------------------------------------------------------
@register
class FixerAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "fixerio"
    config = ProviderConfig(
        provider_id="fixer", category="forex",
        credential_key="FIXER_KEY",
        rate_limit_rpm=10, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, base: str = "USD", **kwargs):
        Fixerio = self._import_from("fixerio", "Fixerio")
        f = Fixerio(access_key=self._get_credential())
        return f.latest(base=base)

    def _normalize(self, raw) -> DataResult:
        rates = raw.get("rates", raw) if isinstance(raw, dict) else {}
        df = pd.DataFrame([{"currency": k, "rate": v} for k, v in rates.items()])
        return DataResult(provider_id="fixer", category="forex",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# CurrencyFreaks — REST
# ---------------------------------------------------------------------------
@register
class CurrencyFreaksAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="currencyfreaks", category="forex",
        credential_key="CURRENCYFREAKS_KEY",
        base_url="https://api.currencyfreaks.com",
        rate_limit_rpm=10, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, base: str = "USD", **kwargs):
        resp = self._get("/latest", params={"apikey": self._get_credential(), "base": base})
        return resp.json()

    def _normalize(self, raw) -> DataResult:
        rates = raw.get("rates", {})
        df = pd.DataFrame([{"currency": k, "rate": float(v)} for k, v in rates.items()])
        return DataResult(provider_id="currencyfreaks", category="forex",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# OANDA Practice — oandapyV20
# ---------------------------------------------------------------------------
@register
class OandaAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "oandapyV20"
    config = ProviderConfig(
        provider_id="oanda", category="forex",
        credential_key="OANDA_KEY",
        rate_limit_rpm=120, ttl_seconds=60, priority="high",
    )

    def _fetch_raw(self, instrument: str = "EUR_USD", granularity: str = "H1",
                   count: int = 500, **kwargs):
        oandapyV20 = self._import_lib()
        InstrumentsCandles = self._import_from("oandapyV20.endpoints.instruments", "InstrumentsCandles")
        api = oandapyV20.API(access_token=self._get_credential(), environment="practice")
        params = {"count": count, "granularity": granularity, "price": "M"}
        r = InstrumentsCandles(instrument, params=params)
        api.request(r)
        return r.response.get("candles", [])

    def _normalize(self, raw) -> DataResult:
        rows = []
        for c in raw:
            mid = c.get("mid", {})
            rows.append({"date": c.get("time"), "open": float(mid.get("o", 0)),
                          "high": float(mid.get("h", 0)), "low": float(mid.get("l", 0)),
                          "close": float(mid.get("c", 0)), "volume": c.get("volume", 0)})
        df = pd.DataFrame(rows)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], utc=True)
        return DataResult(provider_id="oanda", category="forex",
                          fetched_at="", latency_ms=0, success=True, data=df)
