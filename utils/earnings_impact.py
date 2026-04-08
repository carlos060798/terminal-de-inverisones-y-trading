"""
Earnings Impact Matrix.
Cross-references historical earnings dates with price action to measure
how a stock has historically reacted to earnings surprises.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def compute_earnings_impact(ticker: str) -> dict:
    """
    Analyze historical earnings reactions for a ticker.

    Returns dict with:
        - events: DataFrame of past earnings with gap%, eps_actual, eps_estimate, surprise%
        - avg_gap_up: avg move on beats
        - avg_gap_down: avg move on misses
        - beat_rate: % of beats
    """
    try:
        tk = yf.Ticker(ticker)
        # Calendar has upcoming earnings; history is in earnings_history or quarterly_financials
        earnings_hist = tk.earnings_history
        price_hist    = yf.download(ticker, period="5y", interval="1d",
                                    progress=False, auto_adjust=True)["Close"]
    except Exception as e:
        return {"error": str(e)}

    if earnings_hist is None or earnings_hist.empty:
        # Try quarterly_earnings as fallback
        try:
            earnings_hist = yf.Ticker(ticker).quarterly_earnings
            if earnings_hist is None or earnings_hist.empty:
                return {"error": "No hay datos históricos de earnings disponibles."}
            earnings_hist = earnings_hist.reset_index()
        except Exception:
            return {"error": "No hay datos históricos de earnings disponibles."}

    if price_hist.empty:
        return {"error": "No se pudieron descargar precios históricos."}

    price_hist = price_hist.ffill()

    events = []
    for _, row in earnings_hist.iterrows():
        # Try to get the earnings date from the index or a date column
        date_col = None
        for col in ["Earnings Date", "Date", "Quarter"]:
            if col in earnings_hist.columns:
                date_col = col
                break

        if date_col is None:
            continue

        try:
            earn_date = pd.Timestamp(row[date_col])
            earn_date = earn_date.tz_localize(None) if earn_date.tzinfo else earn_date
        except Exception:
            continue

        # Find price day after earnings
        trading_days = price_hist.index
        future = trading_days[trading_days > earn_date]
        past   = trading_days[trading_days <= earn_date]

        if len(future) == 0 or len(past) == 0:
            continue

        day_after   = future[0]
        day_before  = past[-1]
        price_after  = float(price_hist[day_after])
        price_before = float(price_hist[day_before])
        gap_pct = round((price_after / price_before - 1) * 100, 2)

        eps_actual   = row.get("epsActual", row.get("Actual", None))
        eps_estimate = row.get("epsEstimate", row.get("Estimate", None))

        if eps_actual is not None and eps_estimate is not None:
            try:
                surprise_pct = round((float(eps_actual) - float(eps_estimate)) / abs(float(eps_estimate)) * 100, 1) \
                               if float(eps_estimate) != 0 else 0
                beat = float(eps_actual) >= float(eps_estimate)
            except Exception:
                surprise_pct = None
                beat = None
        else:
            surprise_pct = None
            beat = None

        events.append({
            "Fecha": earn_date.strftime("%Y-%m-%d"),
            "EPS Real": eps_actual,
            "EPS Estimado": eps_estimate,
            "Sorpresa (%)": surprise_pct,
            "Gap Post-Earnings (%)": gap_pct,
            "Beat?": "✅" if beat else ("❌" if beat is False else "?"),
        })

    if not events:
        return {"error": "No se pudieron calcular impactos de earnings."}

    df = pd.DataFrame(events).sort_values("Fecha", ascending=False)

    beats  = df[df["Beat?"] == "✅"]["Gap Post-Earnings (%)"]
    misses = df[df["Beat?"] == "❌"]["Gap Post-Earnings (%)"]

    avg_gap_up   = round(beats.mean(), 2) if not beats.empty else 0
    avg_gap_down = round(misses.mean(), 2) if not misses.empty else 0
    beat_rate    = round((df["Beat?"] == "✅").mean() * 100, 1)
    avg_gap_all  = round(df["Gap Post-Earnings (%)"].abs().mean(), 2)

    return {
        "ticker": ticker,
        "events": df,
        "avg_gap_beat": avg_gap_up,
        "avg_gap_miss": avg_gap_down,
        "avg_move": avg_gap_all,
        "beat_rate": beat_rate,
        "n_events": len(df),
    }
