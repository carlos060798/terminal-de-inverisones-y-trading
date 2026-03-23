"""
Multi-source data aggregator for Quantum Retail Terminal.
Combines data from multiple free sources for richer analysis.
Migrated to Data Fabric Engine (v7) backwards-compatible wrapper.
"""

import pandas as pd
from datetime import datetime, timedelta

try:
    import streamlit as st
except ImportError:
    st = None

from adapters.execution_engine import ExecutionEngine

# Module-level instance for non-streamlit contexts
_engine = None

def get_engine():
    global _engine
    if st is not None:
        return _get_st_engine()
    if _engine is None:
        _engine = ExecutionEngine()
    return _engine

if st is not None:
    @st.cache_resource
    def _get_st_engine():
        return ExecutionEngine()

class DataAggregator:
    """Fetches and merges data from multiple free sources using the new Data Fabric."""
    def __init__(self):
        self.engine = get_engine()

    def get_fear_greed_index(self):
        res = self.engine.fetch_one("fear_greed")
        return res.data if res and res.success else None

    def get_crypto_overview(self):
        res = self.engine.fetch_one("coingecko")
        if res and res.success:
            if isinstance(res.data, pd.DataFrame):
                return res.data.to_dict("records")
            return res.data
        return None

    def get_vix(self):
        res = self.engine.fetch_one("cboe_vix")
        if res and res.success:
            return float(res.data) if res.data is not None else None
        return None

    def get_spy_put_call_ratio(self):
        res = self.engine.fetch_one("spy_pcr")
        return res.data if res and res.success else None

    def get_insider_trades(self, ticker):
        res = self.engine.fetch_one("finviz", ticker=ticker)
        return res.data if res and res.success else None

    def get_institutional_holders(self, ticker):
        res = self.engine.fetch_one("inst_holders", ticker=ticker)
        return res.data if res and res.success else None

    def get_options_flow(self, ticker):
        res = self.engine.fetch_one("options_flow", ticker=ticker)
        return res.data if res and res.success else None

    def get_sec_filings(self, ticker):
        res = self.engine.fetch_one("sec_edgar", ticker=ticker)
        if res and res.success:
            if isinstance(res.data, pd.DataFrame):
                return res.data.to_string()[:2000]
            return str(res.data)[:2000]
        return None

_aggregator = None

def get_aggregator():
    global _aggregator
    if _aggregator is None:
        _aggregator = DataAggregator()
    return _aggregator

if st is not None:
    @st.cache_data(ttl=300)
    def cached_fear_greed_index():
        try: return get_aggregator().get_fear_greed_index()
        except Exception: return None

    @st.cache_data(ttl=300)
    def cached_crypto_overview():
        try: return get_aggregator().get_crypto_overview()
        except Exception: return None

    @st.cache_data(ttl=300)
    def cached_vix():
        try: return get_aggregator().get_vix()
        except Exception: return None

    @st.cache_data(ttl=300)
    def cached_spy_put_call_ratio():
        try: return get_aggregator().get_spy_put_call_ratio()
        except Exception: return None
else:
    def cached_fear_greed_index():
        try: return get_aggregator().get_fear_greed_index()
        except Exception: return None

    def cached_crypto_overview():
        try: return get_aggregator().get_crypto_overview()
        except Exception: return None

    def cached_vix():
        try: return get_aggregator().get_vix()
        except Exception: return None

    def cached_spy_put_call_ratio():
        try: return get_aggregator().get_spy_put_call_ratio()
        except Exception: return None
