"""
strategies.py - Reusable strategy functions for advanced backtesting.
Bollinger Band Breakout, Mean Reversion, MACD Crossover,
Walk-Forward analysis, and parameter optimization.
"""
import pandas as pd
import numpy as np
from itertools import product


# ═══════════════════════════════════════════════════════════════
# STRATEGIES
# ═══════════════════════════════════════════════════════════════

def run_bollinger(df, window=20, num_std=2):
    """
    Bollinger Band breakout strategy.
    Buy when price closes above upper band, sell when below lower band.
    Returns DataFrame with Close, Signal, Strategy_Return.
    """
    df = df.copy()
    df["BB_mid"] = df["Close"].rolling(window).mean()
    df["BB_std"] = df["Close"].rolling(window).std()
    df["BB_upper"] = df["BB_mid"] + num_std * df["BB_std"]
    df["BB_lower"] = df["BB_mid"] - num_std * df["BB_std"]

    df["Signal"] = 0
    position = 0
    signals = []
    for i in range(len(df)):
        mid = df["BB_mid"].iloc[i]
        upper = df["BB_upper"].iloc[i]
        lower = df["BB_lower"].iloc[i]
        close = df["Close"].iloc[i]
        if pd.notna(upper) and pd.notna(lower):
            if close > upper and position == 0:
                position = 1
            elif close < lower and position == 1:
                position = 0
        signals.append(position)
    df["Signal"] = signals

    df["Strategy_Return"] = df["Signal"].shift(1) * df["Close"].pct_change()
    df["BuyHold_Return"] = df["Close"].pct_change()
    df["Strategy_Equity"] = (1 + df["Strategy_Return"].fillna(0)).cumprod()
    df["BuyHold_Equity"] = (1 + df["BuyHold_Return"].fillna(0)).cumprod()
    df["Position"] = df["Signal"].diff()
    return df


def run_mean_reversion(df, window=20, threshold=1.5):
    """
    Mean reversion strategy.
    Buy when price is below lower Bollinger band (mean - threshold * std),
    sell when price is above upper band (mean + threshold * std).
    """
    df = df.copy()
    df["MR_mean"] = df["Close"].rolling(window).mean()
    df["MR_std"] = df["Close"].rolling(window).std()
    df["MR_upper"] = df["MR_mean"] + threshold * df["MR_std"]
    df["MR_lower"] = df["MR_mean"] - threshold * df["MR_std"]

    df["Signal"] = 0
    position = 0
    signals = []
    for i in range(len(df)):
        mean_val = df["MR_mean"].iloc[i]
        upper = df["MR_upper"].iloc[i]
        lower = df["MR_lower"].iloc[i]
        close = df["Close"].iloc[i]
        if pd.notna(upper) and pd.notna(lower):
            if close < lower and position == 0:
                position = 1  # Buy below lower band
            elif close > upper and position == 1:
                position = 0  # Sell above upper band
        signals.append(position)
    df["Signal"] = signals

    df["Strategy_Return"] = df["Signal"].shift(1) * df["Close"].pct_change()
    df["BuyHold_Return"] = df["Close"].pct_change()
    df["Strategy_Equity"] = (1 + df["Strategy_Return"].fillna(0)).cumprod()
    df["BuyHold_Equity"] = (1 + df["BuyHold_Return"].fillna(0)).cumprod()
    df["Position"] = df["Signal"].diff()
    return df


def run_macd_crossover(df, fast=12, slow=26, signal=9):
    """
    MACD crossover strategy.
    Buy when MACD crosses above signal line, sell when crosses below.
    """
    df = df.copy()
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    df["Signal"] = 0
    position = 0
    signals = []
    for i in range(len(df)):
        macd_val = df["MACD"].iloc[i]
        sig_val = df["MACD_signal"].iloc[i]
        if pd.notna(macd_val) and pd.notna(sig_val):
            if macd_val > sig_val and position == 0:
                position = 1
            elif macd_val < sig_val and position == 1:
                position = 0
        signals.append(position)
    df["Signal"] = signals

    df["Strategy_Return"] = df["Signal"].shift(1) * df["Close"].pct_change()
    df["BuyHold_Return"] = df["Close"].pct_change()
    df["Strategy_Equity"] = (1 + df["Strategy_Return"].fillna(0)).cumprod()
    df["BuyHold_Equity"] = (1 + df["BuyHold_Return"].fillna(0)).cumprod()
    df["Position"] = df["Signal"].diff()
    return df


# ═══════════════════════════════════════════════════════════════
# WALK-FORWARD ANALYSIS
# ═══════════════════════════════════════════════════════════════

def walk_forward(df, strategy_fn, params, n_splits=5):
    """
    Walk-forward analysis: split data into n train/test periods,
    run strategy on each, return combined results.

    Args:
        df: DataFrame with at least a 'Close' column
        strategy_fn: callable that takes (df, **params) -> df with Strategy_Return
        params: dict of strategy parameters
        n_splits: number of train/test splits

    Returns:
        dict with:
            - 'folds': list of dicts with train_return, test_return, train_sharpe, test_sharpe
            - 'combined_test_return': overall test return
            - 'stability': std of test returns across folds
    """
    n = len(df)
    fold_size = n // n_splits
    if fold_size < 50:
        return {"folds": [], "combined_test_return": 0, "stability": 0,
                "error": "Datos insuficientes para walk-forward"}

    folds = []
    test_returns = []

    for i in range(n_splits):
        # Train: all data up to fold boundary; Test: the fold
        train_end = fold_size * (i + 1)
        test_start = train_end
        test_end = min(train_end + fold_size, n)

        if test_start >= n or test_end - test_start < 10:
            continue

        train_df = df.iloc[:train_end].copy()
        test_df = df.iloc[test_start:test_end].copy()

        try:
            # Run strategy on train
            train_result = strategy_fn(train_df, **params)
            train_ret = (train_result["Strategy_Equity"].iloc[-1] - 1) * 100
            train_strat = train_result["Strategy_Return"].dropna()
            train_sharpe = (train_strat.mean() / train_strat.std() * np.sqrt(252)) if train_strat.std() > 0 else 0

            # Run strategy on test
            test_result = strategy_fn(test_df, **params)
            test_ret = (test_result["Strategy_Equity"].iloc[-1] - 1) * 100
            test_strat = test_result["Strategy_Return"].dropna()
            test_sharpe = (test_strat.mean() / test_strat.std() * np.sqrt(252)) if test_strat.std() > 0 else 0

            folds.append({
                "fold": i + 1,
                "train_return": round(train_ret, 2),
                "test_return": round(test_ret, 2),
                "train_sharpe": round(float(train_sharpe), 2),
                "test_sharpe": round(float(test_sharpe), 2),
                "train_size": len(train_df),
                "test_size": len(test_df),
            })
            test_returns.append(test_ret)
        except Exception:
            continue

    combined_test_return = np.mean(test_returns) if test_returns else 0
    stability = np.std(test_returns) if len(test_returns) > 1 else 0

    return {
        "folds": folds,
        "combined_test_return": round(float(combined_test_return), 2),
        "stability": round(float(stability), 2),
    }


# ═══════════════════════════════════════════════════════════════
# PARAMETER OPTIMIZATION (Grid Search)
# ═══════════════════════════════════════════════════════════════

def optimize_params(df, strategy_fn, param_grid):
    """
    Grid search over parameter combinations.

    Args:
        df: DataFrame with 'Close' column
        strategy_fn: callable(df, **params) -> df with Strategy_Equity
        param_grid: dict where keys are param names and values are lists of values
                    e.g. {"window": [10, 20, 30], "num_std": [1.5, 2.0, 2.5]}

    Returns:
        DataFrame with columns for each param + 'Return(%)' + 'Sharpe'
    """
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = list(product(*values))

    results = []
    for combo in combos:
        params = dict(zip(keys, combo))
        try:
            result_df = strategy_fn(df, **params)
            total_ret = (result_df["Strategy_Equity"].iloc[-1] - 1) * 100
            strat_ret = result_df["Strategy_Return"].dropna()
            sharpe = (strat_ret.mean() / strat_ret.std() * np.sqrt(252)) if strat_ret.std() > 0 else 0
            row = {k: v for k, v in params.items()}
            row["Return(%)"] = round(total_ret, 2)
            row["Sharpe"] = round(float(sharpe), 2)
            results.append(row)
        except Exception:
            row = {k: v for k, v in params.items()}
            row["Return(%)"] = None
            row["Sharpe"] = None
            results.append(row)

    return pd.DataFrame(results)
