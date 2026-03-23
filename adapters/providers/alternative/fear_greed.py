"""Fear & Greed Index (from alternative.me)"""
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import RestMixin
from adapters.registry import register

@register
class FearGreedAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="fear_greed", category="alternative",
        credential_key="",
        base_url="https://api.alternative.me",
        rate_limit_rpm=60, ttl_seconds=300, priority="medium"
    )

    def _fetch_raw(self, **kwargs):
        resp = self._get("/fng/", params={"limit": 30})
        return resp.json().get("data", [])

    def _normalize(self, raw) -> DataResult:
        if not raw:
            return DataResult(provider_id="fear_greed", category="alternative", fetched_at="", latency_ms=0, success=False, data=None, error="No data")
        res = {
            "value": int(raw[0]["value"]),
            "label": raw[0]["value_classification"],
            "history": [(d["timestamp"], int(d["value"])) for d in raw]
        }
        return DataResult(provider_id="fear_greed", category="alternative",
                          fetched_at="", latency_ms=0, success=True, data=res)
