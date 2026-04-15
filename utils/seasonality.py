"""
Historical Seasonality Engine.
Calculates monthly and weekly return patterns over the last N years
to reveal statistically biased periods for a given asset.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def compute_seasonality(ticker: str, years: int = 10) -> dict:
    """
    Compute monthly and day-of-week seasonality for a ticker.

    Returns:
        - monthly: DataFrame with avg_return_pct, win_rate, count per month
        - weekly:  DataFrame with avg_return_pct, win_rate per weekday
        - best_month, worst_month: str
        - ticker: str
    """
    period = f"{years}y"
    try:
        data = yf.download(ticker, period=period, interval="1d",
                           progress=False, auto_adjust=True)["Close"]
    except Exception as e:
        return {"error": str(e)}

    if data.empty or len(data) < 252:
        return {"error": "Datos históricos insuficientes (mínimo 1 año requerido)."}

    # Monthly returns
    monthly_prices = data.resample("ME").last()
    monthly_returns = monthly_prices.pct_change().dropna() * 100

    month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Sep.", 10: "Oct.", 11: "Nov.", 12: "Dic."
    }

    monthly_stats = []
    for m in range(1, 13):
        mask = monthly_returns.index.month == m
        subset = monthly_returns[mask]
        if len(subset) > 0:
            monthly_stats.append({
                "Mes": month_names[m],
                "Mes_num": m,
                "Retorno Promedio (%)": round(subset.mean(), 2),
                "Win Rate (%)": round((subset > 0).mean() * 100, 1),
                "Obs.": len(subset),
                "Mejor (%)": round(subset.max(), 2),
                "Peor (%)": round(subset.min(), 2),
                "Std Dev (%)": round(subset.std(), 2),
            })

    monthly_df = pd.DataFrame(monthly_stats)

    # Best / worst months
    col = monthly_df["Retorno Promedio (%)"].squeeze()
    best_month  = monthly_df.loc[col.idxmax(), "Mes"]
    worst_month = monthly_df.loc[col.idxmin(), "Mes"]


    # Day-of-week returns
    daily_returns = data.pct_change().dropna() * 100
    day_names = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes"}

    weekly_stats = []
    for d in range(5):
        mask = daily_returns.index.dayofweek == d
        subset = daily_returns[mask]
        if len(subset) > 0:
            weekly_stats.append({
                "Día": day_names[d],
                "Retorno Promedio (%)": round(subset.mean(), 3),
                "Win Rate (%)": round((subset > 0).mean() * 100, 1),
                "Obs.": len(subset),
            })

    weekly_df = pd.DataFrame(weekly_stats)

    # Quarterly analysis
    quarterly = data.resample("QE").last().pct_change().dropna() * 100
    q_names = {1: "Q1 (Ene-Mar)", 2: "Q2 (Abr-Jun)", 3: "Q3 (Jul-Sep)", 4: "Q4 (Oct-Dic)"}
    quarterly_stats = []
    for q in range(1, 5):
        mask = quarterly.index.quarter == q
        subset = quarterly[mask]
        if len(subset) > 0:
            quarterly_stats.append({
                "Trimestre": q_names[q],
                "Retorno Promedio (%)": round(subset.mean(), 2),
                "Win Rate (%)": round((subset > 0).mean() * 100, 1),
                "Obs.": len(subset),
            })

    quarterly_df = pd.DataFrame(quarterly_stats)

    return {
        "ticker": ticker,
        "years": years,
        "monthly": monthly_df,
        "weekly": weekly_df,
        "quarterly": quarterly_df,
        "best_month": best_month,
        "worst_month": worst_month,
    }
