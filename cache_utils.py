"""Cache layer for yfinance calls. Eliminates redundant API requests."""
import streamlit as st
import yfinance as yf
import pandas as pd

@st.cache_data(ttl=300, show_spinner=False)
def get_ticker_info(ticker: str) -> dict:
    """Cached ticker info (5 min TTL)."""
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

@st.cache_data(ttl=300, show_spinner=False)
def get_ticker_price(ticker: str) -> float:
    """Cached last price (5 min TTL)."""
    try:
        return yf.Ticker(ticker).fast_info.get('lastPrice', 0)
    except:
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
    except:
        return {'income': pd.DataFrame(), 'balance': pd.DataFrame(), 'cashflow': pd.DataFrame()}

@st.cache_data(ttl=600, show_spinner=False)
def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Cached price history (10 min TTL)."""
    try:
        return yf.download(ticker, period=period, progress=False)
    except:
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
            except:
                prices[t] = 0.0
        return prices
    except:
        return {t: 0.0 for t in tickers_tuple}

@st.cache_data(ttl=300, show_spinner=False)
def get_dividends(ticker: str) -> pd.Series:
    """Cached dividend history."""
    try:
        return yf.Ticker(ticker).dividends
    except:
        return pd.Series()
