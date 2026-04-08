"""
Market Breadth Dashboard.
Calculates the % of S&P 500 stocks trading above their SMA-50 and SMA-200.
A divergence (index up, breadth down) is a classic institutional warning signal.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st


@st.cache_data(ttl=7200, show_spinner=False)
def get_sp500_tickers() -> list:
    """Fetch S&P 500 tickers from Wikipedia."""
    try:
        table = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", header=0
        )[0]
        tickers = table["Symbol"].str.replace(".", "-", regex=False).tolist()
        return tickers
    except Exception:
        # Fallback: 50 representative tickers
        return [
            "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","BRK-B","JPM","V",
            "UNH","LLY","XOM","JNJ","WMT","MA","AVGO","PG","HD","CVX","MRK",
            "ABBV","PEP","COST","KO","ADBE","CRM","TMO","ACN","MCD","CSCO","ABT",
            "AMD","NKE","LIN","TXN","NEE","DHR","ORCL","HON","PM","IBM","RTX",
            "CAT","GE","AMGN","SPGI","QCOM","INTU","GILD",
        ]


@st.cache_data(ttl=3600, show_spinner=False)
def compute_market_breadth(sample_size: int = 100) -> dict:
    """
    Compute % of stocks above SMA-50 and SMA-200.
    Uses a sample for speed; full 500 can take 2-3 min.
    """
    tickers = get_sp500_tickers()[:sample_size]

    try:
        data = yf.download(
            tickers, period="1y", interval="1d", progress=False, auto_adjust=True
        )["Close"]
    except Exception as e:
        return {"error": str(e)}

    if data.empty:
        return {"error": "No se pudo descargar datos del mercado."}

    data = data.ffill().dropna(axis=1, thresh=int(0.7 * len(data)))

    above_50  = (data.iloc[-1] > data.rolling(50).mean().iloc[-1]).sum()
    above_200 = (data.iloc[-1] > data.rolling(200).mean().iloc[-1]).sum()
    total     = len(data.columns)

    pct_above_50  = round(above_50  / total * 100, 1) if total > 0 else 0
    pct_above_200 = round(above_200 / total * 100, 1) if total > 0 else 0

    # Historical breadth (weekly, last 52 weeks)
    weekly = data.resample("W").last()
    sma50_hist  = weekly.rolling(50 // 5).mean()  # ~10 weeks ≈ 50 days
    sma200_hist = weekly.rolling(40).mean()        # ~40 weeks ≈ 200 days

    pct_50_hist  = (weekly > sma50_hist).sum(axis=1) / weekly.shape[1] * 100
    pct_200_hist = (weekly > sma200_hist).sum(axis=1) / weekly.shape[1] * 100

    # Market signal
    if pct_above_50 >= 70:
        signal_50 = "🟢 Fuerte — Mercado alcista amplio"
    elif pct_above_50 >= 50:
        signal_50 = "🟡 Neutral — Mercado mixto"
    elif pct_above_50 >= 30:
        signal_50 = "🟠 Débil — Posible corrección"
    else:
        signal_50 = "🔴 Muy débil — Capitulación"

    if pct_above_200 >= 70:
        signal_200 = "🟢 Tendencia alcista de largo plazo"
    elif pct_above_200 >= 50:
        signal_200 = "🟡 Tendencia neutral"
    else:
        signal_200 = "🔴 Tendencia bajista dominante"

    # Sector breakdown (use ETF proxies)
    sector_etfs = {
        "Tecnología": "XLK", "Finanzas": "XLF", "Salud": "XLV",
        "Energía": "XLE", "Consumo Disc.": "XLY", "Industria": "XLI",
        "Utilities": "XLU", "Materiales": "XLB", "Real Estate": "XLRE",
        "Consumo Básico": "XLP", "Telecom": "XLC",
    }
    try:
        etf_data = yf.download(
            list(sector_etfs.values()), period="1y", progress=False, auto_adjust=True
        )["Close"].ffill()
        sector_results = {}
        for name, etf in sector_etfs.items():
            if etf in etf_data.columns:
                price = etf_data[etf].iloc[-1]
                sma50  = etf_data[etf].rolling(50).mean().iloc[-1]
                sma200 = etf_data[etf].rolling(200).mean().iloc[-1]
                sector_results[name] = {
                    "etf": etf,
                    "above_50": bool(price > sma50),
                    "above_200": bool(price > sma200),
                    "price": round(price, 2),
                }
    except Exception:
        sector_results = {}

    return {
        "pct_above_50": pct_above_50,
        "pct_above_200": pct_above_200,
        "above_50": int(above_50),
        "above_200": int(above_200),
        "total_analyzed": total,
        "signal_50": signal_50,
        "signal_200": signal_200,
        "hist_50": pct_50_hist,
        "hist_200": pct_200_hist,
        "sectors": sector_results,
    }
