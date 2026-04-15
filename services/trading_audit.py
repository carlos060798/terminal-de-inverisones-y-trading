"""
services/trading_audit.py — Behavioral Trading Audit & Psychological Bias Detector
Enchanced version with Win/Loss streaks and Profit Factor behavioral analysis.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def analyze_behavioral_patterns(trades_df):
    """
    Analyzes a DataFrame of trades for psychological biases.
    Expected columns: trade_date, pnl, ticker, shares.
    """
    if trades_df.empty or len(trades_df) < 3:
        return {
            "revenge_trades": 0,
            "revenge_impact": 0.0,
            "overtrading_score": "Low",
            "fomo_detected": False,
            "discipline_rating": 100,
            "winning_streak": 0,
            "losing_streak": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "expectancy": 0
        }

    # Ensure dates are datetime
    df = trades_df.copy()
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date")
    
    # 1. Revenge Trading Detection
    revenge_count = 0
    revenge_pnl = 0.0
    for i in range(1, len(df)):
        prev_trade = df.iloc[i-1]
        curr_trade = df.iloc[i]
        if prev_trade["pnl"] < 0:
            time_diff = (curr_trade["trade_date"] - prev_trade["trade_date"]).total_seconds() / 3600
            if 0 < time_diff < 4:
                revenge_count += 1
                revenge_pnl += curr_trade["pnl"]
    
    # 2. Overtrading (Too many trades in a single day)
    trades_per_day = df.groupby(df["trade_date"].dt.date).size()
    max_trades_day = trades_per_day.max()
    overtrading = "High" if max_trades_day > 8 else ("Medium" if max_trades_day > 4 else "Low")
    
    # 3. Streaks (Win/Loss runs)
    pnl_series = df["pnl"].tolist()
    win_streak = max_win_streak = 0
    loss_streak = max_loss_streak = 0
    
    for val in pnl_series:
        if val > 0:
            win_streak += 1
            loss_streak = 0
            max_win_streak = max(max_win_streak, win_streak)
        elif val < 0:
            loss_streak += 1
            win_streak = 0
            max_loss_streak = max(max_loss_streak, loss_streak)
            
    # 4. Expectations & Profit Metrics
    wins = df[df["pnl"] > 0]["pnl"]
    losses = df[df["pnl"] < 0]["pnl"]
    
    avg_win = wins.mean() if not wins.empty else 0
    avg_loss = abs(losses.mean()) if not losses.empty else 0
    win_rate = len(wins) / len(df)
    
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    # 5. Discipline Rating
    discipline = max(0, 100 - (revenge_count * 15) - (10 if overtrading == "High" else 0))
    
    return {
        "revenge_trades": revenge_count,
        "revenge_impact": revenge_pnl,
        "overtrading_score": overtrading,
        "max_trades_single_day": int(max_trades_day),
        "discipline_rating": discipline,
        "winning_streak": max_win_streak,
        "losing_streak": max_loss_streak,
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "expectancy": float(expectancy),
        "rr_ratio": float(avg_win / avg_loss) if avg_loss > 0 else 0,
        "advice": _get_behavioral_advice(revenge_count, overtrading, max_loss_streak)
    }

def _get_behavioral_advice(revenge_count, overtrading, loss_streak):
    if revenge_count > 1:
        return "⚠️ REVENGE DETECTED: Estás operando para recuperar pérdidas. ¡Detente!"
    if loss_streak >= 3:
        return "📉 STREAK ALERT: Racha negativa activa. Reduce el tamaño de posición al 50%."
    if overtrading == "High":
        return "🛑 OVERTRADING: Estás operando DEMASIADO. Prioriza calidad sobre cantidad."
    return "✅ MANTÉN EL RITMO: Tu psicología operativa está bajo control."
