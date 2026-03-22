"""
Multi-source data aggregator for Quantum Retail Terminal.
Combines data from multiple free sources for richer analysis.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta

try:
    import yfinance as yf
except ImportError:
    yf = None


class DataAggregator:
    """Fetches and merges data from multiple free sources."""

    # ── Fear & Greed Index (alternative.me — free, no key) ──────────────
    def get_fear_greed_index(self):
        """CNN Fear & Greed Index via alternative.me API (free, no key)."""
        try:
            r = requests.get(
                "https://api.alternative.me/fng/?limit=30", timeout=10
            )
            data = r.json()["data"]
            return {
                "value": int(data[0]["value"]),
                "label": data[0]["value_classification"],
                "history": [
                    (d["timestamp"], int(d["value"])) for d in data
                ],
            }
        except Exception:
            return None

    # ── Crypto Overview (CoinGecko — free, no key, 30 req/min) ──────────
    def get_crypto_overview(self):
        """Top cryptos from CoinGecko API (free, no key, 30 req/min)."""
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 20,
                    "sparkline": "true",
                },
                timeout=10,
            )
            return r.json()
        except Exception:
            return None

    # ── VIX current level (via yfinance ^VIX) ───────────────────────────
    def get_vix(self):
        """Current VIX level from yfinance."""
        if not yf:
            return None
        try:
            tk = yf.Ticker("^VIX")
            price = tk.fast_info.last_price
            return round(price, 2) if price else None
        except Exception:
            return None

    # ── SPY Put/Call Ratio (options volume via yfinance) ────────────────
    def get_spy_put_call_ratio(self):
        """Put/Call ratio for SPY from yfinance options data."""
        if not yf:
            return None
        try:
            tk = yf.Ticker("SPY")
            dates = tk.options[:1]  # nearest expiry
            if not dates:
                return None
            chain = tk.option_chain(dates[0])
            calls_vol = chain.calls["volume"].sum() if "volume" in chain.calls else 0
            puts_vol = chain.puts["volume"].sum() if "volume" in chain.puts else 0
            ratio = puts_vol / max(calls_vol, 1)
            return {
                "ratio": round(ratio, 3),
                "calls_vol": int(calls_vol),
                "puts_vol": int(puts_vol),
                "expiry": dates[0],
            }
        except Exception:
            return None

    # ── Insider Trades (finvizfinance) ──────────────────────────────────
    def get_insider_trades(self, ticker):
        """Insider trading data from finvizfinance."""
        try:
            from finvizfinance.quote import finvizfinance
            stock = finvizfinance(ticker)
            df = stock.ticker_inside_trader()
            if df is not None and not df.empty:
                return df.head(15)
            return None
        except Exception:
            return None

    # ── Institutional Holders (yfinance) ────────────────────────────────
    def get_institutional_holders(self, ticker):
        """Top institutional holders from yfinance."""
        if not yf:
            return None
        try:
            t = yf.Ticker(ticker)
            inst = t.institutional_holders
            if inst is not None and not inst.empty:
                return inst.head(10)
            return None
        except Exception:
            return None

    # ── Options Flow (yfinance — next 3 expiry dates) ──────────────────
    def get_options_flow(self, ticker):
        """Options data from yfinance for the next 3 expiry dates."""
        if not yf:
            return None
        try:
            t = yf.Ticker(ticker)
            dates = t.options[:3]  # Next 3 expiry dates
            result = []
            for d in dates:
                chain = t.option_chain(d)
                calls_vol = (
                    chain.calls["volume"].sum()
                    if "volume" in chain.calls
                    else 0
                )
                puts_vol = (
                    chain.puts["volume"].sum()
                    if "volume" in chain.puts
                    else 0
                )
                result.append(
                    {
                        "expiry": d,
                        "calls_vol": int(calls_vol) if pd.notna(calls_vol) else 0,
                        "puts_vol": int(puts_vol) if pd.notna(puts_vol) else 0,
                        "put_call_ratio": round(
                            puts_vol / max(calls_vol, 1), 3
                        ),
                    }
                )
            return result if result else None
        except Exception:
            return None

    # ── SEC Filings (SEC EDGAR — free, no key) ─────────────────────────
    def get_sec_filings(self, ticker):
        """Recent SEC filings from SEC EDGAR (free, no key)."""
        try:
            headers = {"User-Agent": "QuantumTerminal admin@example.com"}
            r = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={
                    "q": ticker,
                    "dateRange": "custom",
                    "startdt": "2024-01-01",
                    "forms": "10-K,10-Q,8-K",
                },
                headers=headers,
                timeout=10,
            )
            if r.status_code == 200:
                return r.text[:2000]
            return None
        except Exception:
            return None


# Singleton instance for use across the app
_aggregator = None


def get_aggregator():
    """Return singleton DataAggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = DataAggregator()
    return _aggregator
