import vectorbt as vbt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from finterm.charts.base import COLORS, apply_theme

def run_sma_crossover(df: pd.DataFrame, fast=20, slow=50):
    """
    Standard SMA Crossover strategy using vectorbt.
    """
    if df.empty: return None
    
    price = df['Close']
    fast_ma = vbt.MA.run(price, fast)
    slow_ma = vbt.MA.run(price, slow)
    
    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)
    
    portfolio = vbt.Portfolio.from_signals(price, entries, exits, init_cash=10000)
    return portfolio

def run_rsi_strategy(df: pd.DataFrame, lower=30, upper=70):
    """
    Mean reversion RSI strategy.
    """
    if df.empty: return None
    
    price = df['Close']
    rsi = vbt.RSI.run(price)
    
    entries = rsi.rsi_crossed_below(lower)
    exits = rsi.rsi_crossed_above(upper)
    
    portfolio = vbt.Portfolio.from_signals(price, entries, exits, init_cash=10000)
    return portfolio

def get_portfolio_stats(portfolio):
    """
    Extracts key performance metrics from vbt portfolio.
    """
    if portfolio is None: return {}
    
    stats = portfolio.stats()
    return {
        "Total Return (%)": stats['Total Return [%]'],
        "Benchmark Return (%)": stats['Benchmark Return [%]'],
        "Sharpe Ratio": stats['Sharpe Ratio'],
        "Max Drawdown (%)": stats['Max Drawdown [%]'],
        "Win Rate (%)": stats['Win Rate [%]'],
        "Total Trades": stats['Total Trades']
    }

def create_backtest_chart(portfolio):
    """
    Creates a performance visualization.
    """
    if portfolio is None: return None
    
    # Value over time
    fig = portfolio.plot(subplots=['cum_returns', 'drawdowns'])
    fig.update_layout(template="plotly_dark", height=600)
    return apply_theme(fig)
