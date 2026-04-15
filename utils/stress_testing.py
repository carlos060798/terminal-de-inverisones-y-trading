"""
utils/stress_testing.py — Black Swan & Crisis Portfolio Scenario Simulator
Maps historical market shocks onto current portfolio holdings.
"""
import pandas as pd

CRISES = {
    "2008 Financial Crisis": {"market": -0.56, "multiplier": 1.2, "desc": "Housing bubble collapse, high systemic risk."},
    "2020 Covid Crash": {"market": -0.34, "multiplier": 1.5, "desc": "Fastest 30% drop in history, high volatility."},
    "2000 Dot-com Bubble": {"market": -0.49, "multiplier": 2.0, "desc": "Tech bubble burst. Growth stocks drop 80%+."},
    "Volmageddon (2018)": {"market": -0.10, "multiplier": 3.0, "desc": "VIX spike, short-term liquidity shock."},
}

def simulate_crisis(portfolio_df, prices_map, beta=1.0):
    """
    portfolio_df: DataFrame with 'ticker', 'shares', 'avg_cost'.
    prices_map: dict of {ticker: current_price}.
    beta: average portfolio beta vs market.
    """
    if portfolio_df.empty:
        return []
    
    total_val = sum(row['shares'] * prices_map.get(row['ticker'], 0) for _, row in portfolio_df.iterrows())
    if total_val == 0:
        return []

    results = []
    for name, shock in CRISES.items():
        # Scenarios use Beta to estimate sensitivity
        # For Dot-com (Tech), if ticker is Tech, multiplier is higher.
        mkt_drop = shock["market"]
        impact = mkt_drop * beta
        
        # Estimate new portfolio value
        pnl_est = total_val * impact
        
        results.append({
            "scenario": name,
            "mkt_drop": mkt_drop,
            "est_impact": impact,
            "pnl_lost": pnl_est,
            "survival_score": max(0, 100 + (impact * 100)), # impact is negative
            "description": shock["desc"]
        })
        
    return results

def get_sector_beta_proxies():
    return {
        "Technology": 1.4,
        "Financial Services": 1.2,
        "Healthcare": 0.8,
        "Energy": 1.1,
        "Consumer Cyclical": 1.3,
        "Consumer Defensive": 0.6,
        "Utilities": 0.5,
        "Communication Services": 1.2
    }
