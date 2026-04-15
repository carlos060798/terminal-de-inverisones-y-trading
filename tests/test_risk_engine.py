import pytest
import pandas as pd
import numpy as np
from utils import risk_engine

def test_correlation_alerts():
    # Create two identical tickers and one independent
    data = {
        "AAPL": np.random.normal(0, 0.01, 100),
        "MSFT": np.random.normal(0, 0.01, 100),
        "SPY": np.random.normal(0, 0.005, 100)
    }
    # Force AAPL and MSFT to be nearly identical
    data["MSFT"] = data["AAPL"] * 0.999 + np.random.normal(0, 0.0001, 100)
    
    df = pd.DataFrame(data)
    matrix, alerts = risk_engine.analyze_correlation(df, threshold=0.9)
    
    assert len(alerts) >= 1
    assert alerts[0]["tickers"] == ("AAPL", "MSFT")
    assert alerts[0]["correlation"] > 0.9

def test_var_calculation():
    # Return of exactly -1% every day
    data = {
        "TICK": [-0.01] * 100,
        "SPY": [0.0] * 100
    }
    df = pd.DataFrame(data)
    weights = {"TICK": 1.0}
    
    res = risk_engine.calculate_advanced_var(df, weights, confidence=0.95, portfolio_value=1000)
    
    # Historical VaR should be -1%
    assert pytest.approx(res["var_hist_pct"], 0.001) == -0.01
    assert pytest.approx(res["var_hist_val"], 0.001) == -10.0

def test_beta_logic():
    # Portafolio that moves exactly 2x benchmark
    bench = np.random.normal(0, 0.01, 100)
    port = bench * 2.0
    
    data = {
        "TICK": port,
        "SPY": bench
    }
    df = pd.DataFrame(data)
    weights = {"TICK": 1.0}
    
    res = risk_engine.calculate_exposure_metrics(df, weights, benchmark="SPY")
    
    assert pytest.approx(res["beta"], 0.1) == 2.0
    assert res["r_squared"] > 0.9

def test_sharpe_ratio():
    # Portfolio with constant 1% gain per day (ann ~ 252%)
    # Risk free 5%
    data = {
        "TICK": [0.01] * 252,
    }
    df = pd.DataFrame(data)
    weights = {"TICK": 1.0}
    
    res = risk_engine.calculate_performance_profiler(df, weights, risk_free_rate=0.05)
    
    # With zero volatility (constant 1%), Sharpe is undefined or huge. 
    # Let's add tiny noise
    df["TICK"] += np.random.normal(0, 0.0001, 252)
    res = risk_engine.calculate_performance_profiler(df, weights, risk_free_rate=0.05)
    
    assert res["sharpe"] > 10 # Extremely efficient
