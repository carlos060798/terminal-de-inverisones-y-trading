"""Polygon.io — polygon-api-client (REST)"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import RestMixin
from adapters.registry import register


@register
class PolygonAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="polygon", category="stocks",
        credential_key="POLYGON_API_KEY",
        base_url="https://api.polygon.io/v2",
        rate_limit_rpm=5, ttl_seconds=60, priority="high",
    )

    def _fetch_raw(self, ticker: str = "AAPL", from_date: str = "2024-01-01",
                   to_date: str = "2024-12-31", **kwargs):
        resp = self._get(
            f"/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}",
            params={"apiKey": self._get_credential(), "adjusted": "true", "limit": "5000"},
        )
        return resp.json().get("results", [])

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw).rename(columns={
            "t": "date", "o": "open", "h": "high",
            "l": "low", "c": "close", "v": "volume",
        })
        df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
        df = df.sort_values("date")
        return DataResult(
            provider_id="polygon", category="stocks",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
