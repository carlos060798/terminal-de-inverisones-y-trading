"""
utils/risk_engine.py — Advanced Portfolio Risk Management Engine (Institutional Grade)
Calculates: Correlation, VaR, Alpha/Beta, Sharpe, Sortino, Factor Attribution, and Efficient Frontier.
Designed for local hardware efficiency (i5-1035G1).
"""
import pandas as pd
import numpy as np
import yfinance as yf
import statsmodels.api as sm
from scipy.stats import norm
from pypfopt import EfficientFrontier, risk_models, expected_returns
import plotly.graph_objects as go
import plotly.express as px
from diskcache import Cache
import os

# --- 0. INITIALIZATION & CACHE ---
cache_dir = os.path.join(os.getcwd(), ".cache", "risk_engine")
cache = Cache(cache_dir)

def get_historical_returns(tickers, period="1y", benchmark="SPY"):
    """
    Downloads adjusted close prices and calculates daily returns.
    Uses diskcache to avoid redundant downloads within a 24h window.
    """
    if not tickers:
        return pd.DataFrame()
    
    # Sort and create a unique key for caching
    all_tickers = sorted(list(set(tickers + [benchmark])))
    cache_key = f"returns_{'-'.join(all_tickers)}_{period}"
    
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    try:
        # Download in batch for efficiency
        data = yf.download(all_tickers, period=period, progress=False)["Close"]
        
        # Handle single ticker case (returns Series instead of DataFrame in some yf versions)
        if isinstance(data, pd.Series):
            data = data.to_frame(all_tickers[0])
            
        returns = data.pct_change().dropna()
        
        # Store in cache for 24 hours (86400 seconds)
        cache.set(cache_key, returns, expire=86400)
        return returns
    except Exception as e:
        print(f"[RISK-ENGINE] Data Error: {e}")
        return pd.DataFrame()

# --- 1. CORRELATION ANALYSIS ---
def analyze_correlation(returns_df, threshold=0.85):
    """
    Calculates Pearson correlation matrix and identifies high concentration alerts.
    """
    if returns_df.empty:
        return pd.DataFrame(), []
    
    # Exclude non-ticker columns if any
    corr_matrix = returns_df.corr(method='pearson')
    
    # Identify alerts (avoiding self-correlation and duplicates)
    alerts = []
    tickers = [c for c in corr_matrix.columns if c != "SPY"]
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            t1, t2 = tickers[i], tickers[j]
            val = corr_matrix.loc[t1, t2]
            if abs(val) > threshold:
                alerts.append({
                    "tickers": (t1, t2),
                    "correlation": val,
                    "type": "Concentración" if val > 0 else "Cobertura Natural"
                })
    
    return corr_matrix, alerts

# --- 2. DYNAMIC VaR & CVaR ---
def calculate_advanced_var(returns_df, weights, confidence=0.95, portfolio_value=10000):
    """
    Calculates Value at Risk using three methods: Historical, Parametric, and CVaR.
    Returns results in % and currency.
    """
    if returns_df.empty or not weights:
        return {}

    # 1. Prepare Portfolio Returns
    available = [t for t in weights.keys() if t in returns_df.columns]
    if not available: return {}
    
    w_array = np.array([weights[t] for t in available])
    w_array = w_array / w_array.sum() # Normalize
    
    port_returns = (returns_df[available] * w_array).sum(axis=1)
    
    # --- Historical VaR ---
    var_hist_pct = np.percentile(port_returns, 100 * (1 - confidence))
    
    # --- Parametric VaR (Normal Distribution) ---
    mu = port_returns.mean()
    std = port_returns.std()
    var_param_pct = norm.ppf(1 - confidence, mu, std)
    
    # --- CVaR (Expected Shortfall) ---
    cvar_pct = port_returns[port_returns <= var_hist_pct].mean()
    
    return {
        "var_hist_pct": var_hist_pct,
        "var_hist_val": var_hist_pct * portfolio_value,
        "var_param_pct": var_param_pct,
        "var_param_val": var_param_pct * portfolio_value,
        "cvar_pct": cvar_pct,
        "cvar_val": cvar_pct * portfolio_value,
        "confidence": confidence
    }

# --- 3. BETA & ALPHA ATTRIBUTION ---
def calculate_exposure_metrics(returns_df, weights, benchmark="SPY"):
    """
    Measures sensitivity and skill (Alpha) using OLS.
    """
    if returns_df.empty or benchmark not in returns_df.columns:
        return {}
        
    available = [t for t in weights.keys() if t in returns_df.columns]
    if not available: return {}
    
    w_array = np.array([weights[t] for t in available])
    w_array = w_array / w_array.sum()
    
    port_returns = (returns_df[available] * w_array).sum(axis=1)
    bench_returns = returns_df[benchmark]
    
    # Regress: Port ~ Bench + Alpha
    X = sm.add_constant(bench_returns)
    model = sm.OLS(port_returns, X).fit()
    
    alpha_daily = model.params.iloc[0]
    beta = model.params.iloc[1]
    r2 = model.rsquared
    
    return {
        "beta": beta,
        "alpha_annual": alpha_daily * 252,
        "r_squared": r2,
        "tracking_error": (port_returns - bench_returns).std() * np.sqrt(252),
        "total_return": (1 + port_returns).prod() - 1,
        "bench_return": (1 + bench_returns).prod() - 1
    }

# --- 4. PERFORMANCE RATIOS ---
def calculate_performance_profiler(returns_df, weights, risk_free_rate=0.05):
    """
    Calculates efficiency ratios: Sharpe, Sortino, Calmar.
    """
    if returns_df.empty or not weights:
        return {}
        
    available = [t for t in weights.keys() if t in returns_df.columns]
    w_array = np.array([weights[t] for t in available])
    w_array = w_array / w_array.sum()
    port_returns = (returns_df[available] * w_array).sum(axis=1)
    
    # Annualized Metrics
    ann_return = port_returns.mean() * 252
    ann_vol = port_returns.std() * np.sqrt(252)
    
    # Sharpe
    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0
    
    # Sortino (Downside risk only)
    downside_returns = port_returns[port_returns < 0]
    downside_std = downside_returns.std() * np.sqrt(252)
    sortino = (ann_return - risk_free_rate) / downside_std if downside_std > 0 else 0
    
    # Max Drawdown
    cum_returns = (1 + port_returns).cumprod()
    peak = cum_returns.cummax()
    drawdown = (cum_returns - peak) / peak
    max_dd = drawdown.min()
    
    # Calmar
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0
    
    return {
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": max_dd,
        "ann_return": ann_return,
        "ann_vol": ann_vol
    }

# --- 5. FACTOR ATTRIBUTION (WATERFALL) ---
def get_factor_attribution(stats_dict):
    """
    Descomposes return into Beta contribution and Alpha contribution.
    """
    total = stats_dict.get("total_return", 0)
    beta = stats_dict.get("beta", 0)
    bench = stats_dict.get("bench_return", 0)
    
    beta_contribution = beta * bench
    alpha_contribution = total - beta_contribution
    
    return {
        "total": total,
        "beta_contrib": beta_contribution,
        "alpha_contrib": alpha_contribution
    }

# --- 6. EFFICIENT FRONTIER ---
def calculate_efficient_frontier(returns_df, current_weights):
    """
    Uses PyPortfolioOpt to find the Max Sharpe and Min Vol portfolios.
    """
    if returns_df.empty:
        return {}
        
    tickers = [c for c in returns_df.columns if c != "SPY"]
    if not tickers: return {}
    
    mu = expected_returns.mean_historical_return(returns_df[tickers])
    S = risk_models.sample_cov(returns_df[tickers])
    
    try:
        # Max Sharpe
        ef = EfficientFrontier(mu, S)
        raw_weights_max = ef.max_sharpe()
        clean_weights_max = ef.clean_weights()
        perf_max = ef.portfolio_performance()
        
        # Min Volatility
        ef_min = EfficientFrontier(mu, S)
        raw_weights_min = ef_min.min_volatility()
        clean_weights_min = ef_min.clean_weights()
        perf_min = ef_min.portfolio_performance()
        
        return {
            "max_sharpe_weights": list(clean_weights_max.items()),
            "max_sharpe_perf": perf_max,
            "min_vol_weights": list(clean_weights_min.items()),
            "min_vol_perf": perf_min
        }
    except Exception as e:
        print(f"[RISK-ENGINE] Frontier Error: {e}")
        return {}

# --- 7. REBALANCE ENGINE ---
def calculate_rebalance_needs(wl_df, prices_map, total_val):
    """
    Calculates the difference between current and target weights.
    Generates action table: BUY/SELL shares.
    """
    if wl_df.empty or total_val <= 0:
        return pd.DataFrame()
    
    results = []
    for _, row in wl_df.iterrows():
        ticker = row["ticker"]
        target_w = row.get("target_weight", 0.0)
        
        # Skip if no target is defined
        if target_w <= 0:
            continue
            
        current_price = prices_map.get(ticker, {}).get("price", 0)
        if current_price <= 0:
            import yfinance as yf
            try:
                current_price = yf.Ticker(ticker).fast_info.last_price or 0
            except:
                continue
        
        if current_price <= 0:
            continue

        target_val_pos = total_val * (target_w / 100.0)
        current_val_pos = row["shares"] * current_price
        diff_val = target_val_pos - current_val_pos
        diff_shares = diff_val / current_price
        
        action = "BUY" if diff_shares > 0 else "SELL"
        
        results.append({
            "ticker": ticker,
            "current_w": (current_val_pos / total_val) * 100,
            "target_w": target_w,
            "diff_val": diff_val,
            "diff_shares": diff_shares,
            "action": action
        })
        
    return pd.DataFrame(results)
