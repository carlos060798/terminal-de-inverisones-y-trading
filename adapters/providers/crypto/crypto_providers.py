"""
Crypto providers: Binance, CoinGecko, CoinMarketCap, Kraken, CryptoCompare, Messari
"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin, RestMixin
from adapters.registry import register


# ---------------------------------------------------------------------------
# Binance — python-binance
# ---------------------------------------------------------------------------
@register
class BinanceAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "binance.client"
    config = ProviderConfig(
        provider_id="binance", category="crypto",
        credential_key="BINANCE_API_KEY",
        rate_limit_rpm=1200, ttl_seconds=5, priority="realtime",
    )

    def _fetch_raw(self, symbol: str = "BTCUSDT", interval: str = "1h",
                   limit: int = 500, **kwargs):
        Client = self._import_from("binance.client", "Client")
        c = Client(api_key=self._get_credential())
        return c.get_klines(symbol=symbol, interval=interval, limit=limit)

    def _normalize(self, raw) -> DataResult:
        cols = ["open_time","open","high","low","close","volume",
                "close_time","quote_vol","trades","taker_buy_base",
                "taker_buy_quote","ignore"]
        df = pd.DataFrame(raw, columns=cols)
        df["date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        return DataResult(provider_id="binance", category="crypto",
                          fetched_at="", latency_ms=0, success=True,
                          data=df[["date","open","high","low","close","volume"]])


# ---------------------------------------------------------------------------
# CoinGecko — pycoingecko (migrated from data_sources.py)
# ---------------------------------------------------------------------------
@register
class CoinGeckoAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "pycoingecko"
    config = ProviderConfig(
        provider_id="coingecko", category="crypto",
        credential_key="",
        rate_limit_rpm=30, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, ids: str = "bitcoin,ethereum", vs_currency: str = "usd",
                   per_page: int = 20, **kwargs):
        CoinGeckoAPI = self._import_from("pycoingecko", "CoinGeckoAPI")
        cg = CoinGeckoAPI()
        return cg.get_coins_markets(vs_currency=vs_currency, per_page=per_page)

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        return DataResult(provider_id="coingecko", category="crypto",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# CoinMarketCap — REST
# ---------------------------------------------------------------------------
@register
class CoinMarketCapAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="coinmarketcap", category="crypto",
        credential_key="CMC_API_KEY",
        base_url="https://pro-api.coinmarketcap.com/v1",
        rate_limit_rpm=30, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, limit: int = 20, **kwargs):
        resp = self._get("/cryptocurrency/listings/latest",
                         params={"limit": limit, "convert": "USD"},
                         headers={"X-CMC_PRO_API_KEY": self._get_credential()})
        return resp.json().get("data", [])

    def _normalize(self, raw) -> DataResult:
        rows = []
        for coin in raw:
            quote = coin.get("quote", {}).get("USD", {})
            rows.append({"symbol": coin["symbol"], "name": coin["name"],
                          "price": quote.get("price"), "change_24h": quote.get("percent_change_24h"),
                          "market_cap": quote.get("market_cap")})
        return DataResult(provider_id="coinmarketcap", category="crypto",
                          fetched_at="", latency_ms=0, success=True, data=pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# Kraken — krakenex
# ---------------------------------------------------------------------------
@register
class KrakenAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "krakenex"
    config = ProviderConfig(
        provider_id="kraken", category="crypto",
        credential_key="",
        rate_limit_rpm=60, ttl_seconds=30, priority="high",
    )

    def _fetch_raw(self, pair: str = "XXBTZUSD", **kwargs):
        krakenex = self._import_lib()
        k = krakenex.API()
        return k.query_public("Ticker", {"pair": pair})

    def _normalize(self, raw) -> DataResult:
        result = raw.get("result", {})
        rows = []
        for pair, data in result.items():
            rows.append({"pair": pair, "last": float(data["c"][0]),
                          "bid": float(data["b"][0]), "ask": float(data["a"][0]),
                          "volume": float(data["v"][1])})
        return DataResult(provider_id="kraken", category="crypto",
                          fetched_at="", latency_ms=0, success=True, data=pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# CryptoCompare — cryptocompare library
# ---------------------------------------------------------------------------
@register
class CryptoCompareAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "cryptocompare"
    config = ProviderConfig(
        provider_id="cryptocompare", category="crypto",
        credential_key="CRYPTOCOMPARE_KEY",
        rate_limit_rpm=50, ttl_seconds=300, priority="medium",
    )

    def _fetch_raw(self, symbol: str = "BTC", currency: str = "USD",
                   limit: int = 365, **kwargs):
        cc = self._import_lib()
        return cc.get_historical_price_day(symbol, currency, limit=limit)

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        if "time" in df.columns:
            df["date"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return DataResult(provider_id="cryptocompare", category="crypto",
                          fetched_at="", latency_ms=0, success=True, data=df)


# ---------------------------------------------------------------------------
# Messari — messari-python
# ---------------------------------------------------------------------------
@register
class MessariAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "messari.messari"
    config = ProviderConfig(
        provider_id="messari", category="crypto",
        credential_key="MESSARI_KEY",
        rate_limit_rpm=20, ttl_seconds=3600, priority="low",
    )

    def _fetch_raw(self, asset: str = "bitcoin", **kwargs):
        Messari = self._import_from("messari.messari", "Messari")
        m = Messari(self._get_credential())
        return m.get_asset_metrics(asset)

    def _normalize(self, raw) -> DataResult:
        data = raw.get("data", raw) if isinstance(raw, dict) else raw
        df = pd.json_normalize(data) if isinstance(data, dict) else pd.DataFrame(data if data else [{}])
        return DataResult(provider_id="messari", category="crypto",
                          fetched_at="", latency_ms=0, success=True, data=df)
