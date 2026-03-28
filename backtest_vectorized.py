"""
backtest_vectorized.py - High-Performance Backtesting Engine using vectorbt.
Provides rapid vectorized execution for strategy metrics and optimization.
"""

import pandas as pd
import numpy as np
import vectorbt as vbt

class VectorizedEngine:
    @staticmethod
    def _create_portfolio(df: pd.DataFrame, entries: pd.Series, exits: pd.Series) -> dict:
        """Create a vectorbt portfolio from entry and exit signals."""
        pf = vbt.Portfolio.from_signals(
            close=df['Close'],
            entries=entries,
            exits=exits,
            freq='1D',
            init_cash=10000,
            fees=0.001,
            sl_stop=None,
            tp_stop=None
        )
        return {'pf': pf, 'entries': entries, 'exits': exits}

    @classmethod
    def run_sma_crossover(cls, df: pd.DataFrame, fast: int = 20, slow: int = 50) -> dict:
        """Vectorized SMA Crossover."""
        fast_sma = vbt.MA.run(df['Close'], fast)
        slow_sma = vbt.MA.run(df['Close'], slow)
        entries = fast_sma.ma_crossed_above(slow_sma)
        exits = fast_sma.ma_crossed_below(slow_sma)
        return cls._create_portfolio(df, entries, exits)

    @classmethod
    def run_rsi_strategy(cls, df: pd.DataFrame, period: int = 14, oversold: int = 30, overbought: int = 70) -> dict:
        """Vectorized RSI Strategy."""
        rsi = vbt.RSI.run(df['Close'], window=period)
        entries = rsi.rsi_crossed_below(oversold)
        exits = rsi.rsi_crossed_above(overbought)
        return cls._create_portfolio(df, entries, exits)

    @classmethod
    def run_bollinger(cls, df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> dict:
        """Vectorized Bollinger Breakout."""
        bb = vbt.BBANDS.run(df['Close'], window=window, alpha=num_std)
        # Breakout: close crosses above upper band to enter, crosses below lower band to exit
        entries = df['Close'] > bb.upper
        exits = df['Close'] < bb.lower
        # Prevent continuous signals, we just need cross events
        entries = entries & ~entries.shift(1).fillna(False)
        exits = exits & ~exits.shift(1).fillna(False)
        return cls._create_portfolio(df, entries, exits)

    @classmethod
    def run_mean_reversion(cls, df: pd.DataFrame, window: int = 20, threshold: float = 1.5) -> dict:
        """Vectorized Mean Reversion."""
        bb = vbt.BBANDS.run(df['Close'], window=window, alpha=threshold)
        # Buy when price crosses below lower band, sell when crosses above upper band
        entries = df['Close'] < bb.lower
        exits = df['Close'] > bb.upper
        entries = entries & ~entries.shift(1).fillna(False)
        exits = exits & ~exits.shift(1).fillna(False)
        return cls._create_portfolio(df, entries, exits)

    @classmethod
    def run_macd_crossover(cls, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """Vectorized MACD Crossover."""
        macd_ind = vbt.MACD.run(df['Close'], fast_window=fast, slow_window=slow, signal_window=signal)
        entries = macd_ind.macd_crossed_above(macd_ind.signal)
        exits = macd_ind.macd_crossed_below(macd_ind.signal)
        return cls._create_portfolio(df, entries, exits)

    @staticmethod
    def extract_metrics(result: dict, df: pd.DataFrame) -> dict:
        """Extract key metrics from vectorbt portfolio to match UI requirements."""
        pf = result['pf']
        entries = result['entries']
        exits = result['exits']
        stats = pf.stats()
        
        # Calculate Buy & Hold Return for comparison using exact dates
        bh_return = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100 if len(df) > 0 else 0
        total_return_strat = stats.get('Total Return [%]', 0.0)
        
        return {
            "total_return_strat": total_return_strat,
            "total_return_bh": bh_return,
            "sharpe": stats.get('Sharpe Ratio', 0.0),
            "max_drawdown": stats.get('Max Drawdown [%]', 0.0),
            "buy_signals": int(entries.sum()),
            "sell_signals": int(exits.sum()),
            "sortino": stats.get('Sortino Ratio', 0.0),
            "calmar": stats.get('Calmar Ratio', 0.0),
            "profit_factor": stats.get('Profit Factor', 0.0)
        }

    @staticmethod
    def generate_ui_dataframe(result: dict, df: pd.DataFrame) -> pd.DataFrame:
        """Generate a DataFrame compatible with the existing Plotly UI."""
        pf = result['pf']
        entries = result['entries']
        exits = result['exits']
        
        res_df = df.copy()
        res_df['Strategy_Equity'] = pf.value() / pf.value().iloc[0] # Normalizado a 1
        res_df['BuyHold_Equity'] = (1 + res_df['Close'].pct_change().fillna(0)).cumprod()
        
        # Position mapping
        res_df['Position'] = 0
        res_df.loc[entries, 'Position'] = 1
        res_df.loc[exits, 'Position'] = -1
        
        return res_df


