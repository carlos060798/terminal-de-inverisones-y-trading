"""
Sector Rotation Graph.
Relative Rotation Graphs (RRG) show which sectors are improving/leading/weakening
by plotting Relative Strength vs Relative Momentum vs the SPY benchmark.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st


SECTOR_ETFS = {
    "Tecnología": "XLK",
    "Finanzas": "XLF",
    "Salud": "XLV",
    "Energía": "XLE",
    "Consumo Disc.": "XLY",
    "Industria": "XLI",
    "Utilities": "XLU",
    "Materiales": "XLB",
    "Real Estate": "XLRE",
    "Consumo Básico": "XLP",
    "Telecom": "XLC",
}

QUADRANT_COLORS = {
    "Leading":   "#34d399",   # green
    "Weakening": "#fbbf24",   # yellow
    "Lagging":   "#f87171",   # red
    "Improving": "#60a5fa",   # blue
}


@st.cache_data(ttl=3600, show_spinner=False)
def compute_rrg(benchmark: str = "SPY", period: str = "1y",
                rs_period: int = 12, rm_period: int = 4) -> dict:
    """
    Compute Relative Rotation Graph data for sector ETFs vs benchmark.

    Args:
        benchmark: benchmark ticker (default SPY)
        period: lookback period for download
        rs_period: weeks for relative strength smoothing
        rm_period: weeks for momentum smoothing

    Returns:
        dict with sectors, current quadrant, historical tail (last 8 weeks)
    """
    etfs = list(SECTOR_ETFS.values())
    all_tickers = [benchmark] + etfs

    try:
        prices = yf.download(
            all_tickers, period=period, interval="1wk",
            progress=False, auto_adjust=True
        )["Close"].ffill().dropna()
    except Exception as e:
        return {"error": str(e)}

    if benchmark not in prices.columns:
        return {"error": f"No se pudo obtener datos del benchmark {benchmark}."}

    bench = prices[benchmark]
    results = {}

    for name, etf in SECTOR_ETFS.items():
        if etf not in prices.columns:
            continue
        sector = prices[etf]

        # JdK RS-Ratio: ratio of sector to benchmark, normalized to 100
        raw_rs = (sector / bench) * 100
        rs_ratio = raw_rs / raw_rs.rolling(rs_period).mean() * 100

        # JdK RS-Momentum: rate of change of RS-Ratio
        rs_momentum = rs_ratio / rs_ratio.shift(rm_period) * 100

        # Take last 8 data points for the tail
        tail_len = min(8, len(rs_ratio.dropna()))
        tail_rs  = rs_ratio.dropna().iloc[-tail_len:].values
        tail_mom = rs_momentum.dropna().iloc[-tail_len:].values

        if len(tail_rs) == 0 or len(tail_mom) == 0:
            continue

        current_rs  = float(tail_rs[-1])
        current_mom = float(tail_mom[-1]) if len(tail_mom) > 0 else 100

        # Determine quadrant
        if current_rs >= 100 and current_mom >= 100:
            quadrant = "Leading"
        elif current_rs >= 100 and current_mom < 100:
            quadrant = "Weakening"
        elif current_rs < 100 and current_mom < 100:
            quadrant = "Lagging"
        else:
            quadrant = "Improving"

        results[name] = {
            "etf": etf,
            "rs_ratio": current_rs,
            "rs_momentum": current_mom,
            "quadrant": quadrant,
            "tail_rs": tail_rs.tolist(),
            "tail_mom": tail_mom.tolist(),
        }

    return {
        "sectors": results,
        "benchmark": benchmark,
        "quadrant_colors": QUADRANT_COLORS,
    }
