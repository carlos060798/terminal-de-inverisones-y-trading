"""
Financial Modeling Prep (FMP) Analyzer Adapter.
Obtains Key Metrics and Financial Ratios for fundamental analysis.
"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins.rest_mixin import RestMixin
from adapters.registry import register

@register
class FMPAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="fmp", 
        category="stocks",
        credential_key="FMP_API_KEY",
        base_url="https://financialmodelingprep.com/api/v3",
        rate_limit_rpm=250, # Free tier is generous
        daily_quota=250,
        ttl_seconds=3600, # Fundamentals don't change fast
        priority="high",
    )

    def _fetch_raw(self, ticker: str = "AAPL", **kwargs):
        api_key = self._get_credential()
        
        # 1. Key Metrics (LTM)
        metrics_resp = self._get(f"/key-metrics/{ticker}", params={"limit": 1, "apikey": api_key})
        metrics = metrics_resp.json()
        
        # 2. Ratios (LTM)
        ratios_resp = self._get(f"/ratios/{ticker}", params={"limit": 1, "apikey": api_key})
        ratios = ratios_resp.json()
        
        combined = {
            "metrics": metrics[0] if metrics else {},
            "ratios": ratios[0] if ratios else {}
        }
        return combined

    def _normalize(self, raw: dict) -> DataResult:
        metrics = raw.get("metrics", {})
        ratios = raw.get("ratios", {})
        
        # Consolidate core ratios for the terminal
        data = {
            "pe": ratios.get("priceEarningsRatio"),
            "pb": ratios.get("priceToBookRatio"),
            "roe": ratios.get("returnOnEquity"),
            "roa": ratios.get("returnOnAssets"),
            "quick_ratio": ratios.get("quickRatio"),
            "current_ratio": ratios.get("currentRatio"),
            "debt_to_equity": ratios.get("debtEquityRatio"),
            "net_profit_margin": ratios.get("netProfitMargin"),
            "fcf_yield": metrics.get("freeCashFlowYield"),
            "p_to_fcf": metrics.get("priceToFreeCashFlowsRatio"),
            "market_cap": metrics.get("marketCap"),
        }
        
        return DataResult(
            provider_id="fmp",
            category="stocks",
            fetched_at="",
            latency_ms=0,
            success=True,
            data=data,
        )
