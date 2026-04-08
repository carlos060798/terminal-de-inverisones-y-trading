"""Cache layer for yfinance calls. Eliminates redundant API requests."""
import streamlit as st
import yfinance as yf
import pandas as pd

@st.cache_data(ttl=300, show_spinner=False)
def get_ticker_info(ticker: str) -> dict:
    """Cached ticker info (5 min TTL)."""
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return {}

@st.cache_data(ttl=300, show_spinner=False)
def get_ticker_price(ticker: str) -> float:
    """Cached last price (5 min TTL)."""
    try:
        return yf.Ticker(ticker).fast_info.get('lastPrice', 0)
    except Exception:
        return 0.0

@st.cache_data(ttl=3600, show_spinner=False)
def get_financials(ticker: str) -> dict:
    """Cached financial statements (1 hour TTL)."""
    try:
        tk = yf.Ticker(ticker)
        return {
            'income': tk.income_stmt,
            'balance': tk.balance_sheet,
            'cashflow': tk.cashflow,
        }
    except Exception:
        return {'income': pd.DataFrame(), 'balance': pd.DataFrame(), 'cashflow': pd.DataFrame()}

@st.cache_data(ttl=600, show_spinner=False)
def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Cached price history (10 min TTL)."""
    try:
        return yf.download(ticker, period=period, progress=False)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def get_batch_prices(tickers_tuple: tuple) -> dict:
    """Batch download current prices for multiple tickers. Much faster than individual calls."""
    try:
        data = yf.download(list(tickers_tuple), period="2d", group_by="ticker", progress=False)
        prices = {}
        for t in tickers_tuple:
            try:
                if len(tickers_tuple) == 1:
                    prices[t] = float(data['Close'].iloc[-1])
                else:
                    prices[t] = float(data[t]['Close'].iloc[-1])
            except Exception:
                prices[t] = 0.0
        return prices
    except Exception:
        return {t: 0.0 for t in tickers_tuple}

@st.cache_data(ttl=300, show_spinner=False)
def get_dividends(ticker: str) -> pd.Series:
    """Cached dividend history."""
    try:
        return yf.Ticker(ticker).dividends
    except Exception:
        return pd.Series()

@st.cache_data(ttl=3600, show_spinner=False)
def cached_capital_returns(ticker):
    from valuation import compute_capital_returns
    try:
        return compute_capital_returns(ticker)
    except Exception:
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def cached_health_scores(ticker):
    from valuation import compute_health_scores
    try:
        return compute_health_scores(ticker)
    except Exception:
        return {}
@st.cache_data(ttl=300, show_spinner=False)
def get_batch_prices_and_changes(tickers_tuple):
    """Batch-fetch 5d prices for current price + day change."""
    _ZERO = {"price": 0, "prev": 0, "change_pct": 0}
    try:
        data = yf.download(list(tickers_tuple), period="5d", group_by="ticker", progress=False)
        result = {}
        for t in tickers_tuple:
            try:
                closes = (data["Close"] if len(tickers_tuple) == 1 else data[t]["Close"]).dropna()
                if len(closes) >= 2:
                    result[t] = {"price": float(closes.iloc[-1]), "prev": float(closes.iloc[-2]),
                                 "change_pct": (float(closes.iloc[-1]) / float(closes.iloc[-2]) - 1) * 100}
                elif len(closes) == 1:
                    result[t] = {"price": float(closes.iloc[-1]), "prev": 0, "change_pct": 0}
                else:
                    result[t] = dict(_ZERO)
            except Exception:
                result[t] = dict(_ZERO)
        return result
    except Exception:
        return {t: dict(_ZERO) for t in tickers_tuple}
