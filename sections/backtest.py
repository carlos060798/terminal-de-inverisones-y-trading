"""
sections/backtest.py - Basic Backtesting Engine
SMA Crossover & RSI Oversold strategies on yfinance data
"""
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ui_shared import DARK, dark_layout, fmt, kpi


def _calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _run_sma_crossover(df, fast=20, slow=50):
    """SMA crossover strategy: buy when fast > slow, sell when fast < slow."""
    df = df.copy()
    df["SMA_fast"] = df["Close"].rolling(fast).mean()
    df["SMA_slow"] = df["Close"].rolling(slow).mean()
    df["Signal"] = 0
    df.loc[df["SMA_fast"] > df["SMA_slow"], "Signal"] = 1
    df["Position"] = df["Signal"].diff()
    df["Strategy_Return"] = df["Signal"].shift(1) * df["Close"].pct_change()
    df["BuyHold_Return"] = df["Close"].pct_change()
    df["Strategy_Equity"] = (1 + df["Strategy_Return"].fillna(0)).cumprod()
    df["BuyHold_Equity"] = (1 + df["BuyHold_Return"].fillna(0)).cumprod()
    return df


def _run_rsi_strategy(df, period=14, oversold=30, overbought=70):
    """RSI strategy: buy when RSI < oversold, sell when RSI > overbought."""
    df = df.copy()
    df["RSI"] = _calc_rsi(df["Close"], period)
    df["Signal"] = 0
    position = 0
    signals = []
    for i in range(len(df)):
        rsi_val = df["RSI"].iloc[i]
        if pd.notna(rsi_val):
            if rsi_val < oversold and position == 0:
                position = 1
            elif rsi_val > overbought and position == 1:
                position = 0
        signals.append(position)
    df["Signal"] = signals
    df["Position"] = df["Signal"].diff()
    df["Strategy_Return"] = df["Signal"].shift(1) * df["Close"].pct_change()
    df["BuyHold_Return"] = df["Close"].pct_change()
    df["Strategy_Equity"] = (1 + df["Strategy_Return"].fillna(0)).cumprod()
    df["BuyHold_Equity"] = (1 + df["BuyHold_Return"].fillna(0)).cumprod()
    return df


def _compute_metrics(df):
    """Compute strategy metrics."""
    strat_ret = df["Strategy_Return"].dropna()
    bh_ret = df["BuyHold_Return"].dropna()

    # Strategy metrics
    total_return_strat = (df["Strategy_Equity"].iloc[-1] - 1) * 100
    total_return_bh = (df["BuyHold_Equity"].iloc[-1] - 1) * 100

    sharpe = (strat_ret.mean() / strat_ret.std() * np.sqrt(252)) if strat_ret.std() > 0 else 0

    # Max drawdown
    equity = df["Strategy_Equity"]
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min() * 100

    # Win rate
    trades = df[df["Position"] != 0]
    buy_signals = len(df[df["Position"] == 1])
    sell_signals = len(df[df["Position"] == -1])

    return {
        "total_return_strat": total_return_strat,
        "total_return_bh": total_return_bh,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
    }


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Backtesting Engine</h1>
        <p>SMA Crossover · RSI Oversold/Overbought · Equity Curve vs Buy & Hold</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # Config
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.text_input("Ticker", value="AAPL", placeholder="AAPL").strip().upper()
    with c2:
        period = st.selectbox("Período", ["1y", "2y", "3y", "5y", "10y"], index=1)
    with c3:
        strategy = st.selectbox("Estrategia", ["SMA Crossover", "RSI Oversold/Overbought"])

    # Strategy params
    if strategy == "SMA Crossover":
        pc1, pc2 = st.columns(2)
        fast_period = pc1.number_input("SMA Rápida", min_value=5, max_value=100, value=20, step=5)
        slow_period = pc2.number_input("SMA Lenta", min_value=10, max_value=300, value=50, step=10)
    else:
        pc1, pc2, pc3 = st.columns(3)
        rsi_period = pc1.number_input("Período RSI", min_value=5, max_value=30, value=14, step=1)
        oversold = pc2.number_input("Nivel Sobreventa", min_value=10, max_value=40, value=30, step=5)
        overbought = pc3.number_input("Nivel Sobrecompra", min_value=60, max_value=90, value=70, step=5)

    if st.button("Ejecutar Backtest", type="primary", use_container_width=True):
        if not ticker:
            st.warning("Ingresa un ticker.")
            return

        try:
            with st.spinner(f"Descargando datos de {ticker} y ejecutando backtest…"):
                data = yf.download(ticker, period=period, progress=False)
                if data.empty:
                    st.error(f"No se encontraron datos para {ticker}")
                    return

                # Flatten multi-index columns if present
                if hasattr(data.columns, 'levels'):
                    data.columns = data.columns.get_level_values(0)

                if strategy == "SMA Crossover":
                    df = _run_sma_crossover(data, fast=fast_period, slow=slow_period)
                else:
                    df = _run_rsi_strategy(data, period=rsi_period, oversold=oversold, overbought=overbought)

            metrics = _compute_metrics(df)

            # KPIs
            mk1, mk2, mk3, mk4 = st.columns(4)
            strat_color = "green" if metrics["total_return_strat"] >= 0 else "red"
            bh_color = "green" if metrics["total_return_bh"] >= 0 else "red"
            mk1.markdown(kpi("Retorno Estrategia", f"{metrics['total_return_strat']:+.1f}%", "", strat_color), unsafe_allow_html=True)
            mk2.markdown(kpi("Retorno Buy & Hold", f"{metrics['total_return_bh']:+.1f}%", "", bh_color), unsafe_allow_html=True)
            mk3.markdown(kpi("Sharpe Ratio", f"{metrics['sharpe']:.2f}", "", "blue"), unsafe_allow_html=True)
            mk4.markdown(kpi("Max Drawdown", f"{metrics['max_drawdown']:.1f}%", "", "red"), unsafe_allow_html=True)

            # Alpha
            alpha = metrics["total_return_strat"] - metrics["total_return_bh"]
            alpha_color = "#34d399" if alpha >= 0 else "#f87171"
            alpha_text = "SUPERÓ" if alpha >= 0 else "POR DEBAJO DE"
            st.markdown(f"""
            <div style='background:{alpha_color}20;border:1px solid {alpha_color};border-radius:12px;
                        padding:16px;text-align:center;margin:12px 0;'>
              <span style='color:{alpha_color};font-weight:700;font-size:18px;'>
                Estrategia {alpha_text} Buy & Hold por {abs(alpha):.1f}% (Alpha: {alpha:+.1f}%)
              </span>
            </div>""", unsafe_allow_html=True)

            # Equity curve chart
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                                row_heights=[0.7, 0.3],
                                subplot_titles=["Equity Curve", "Drawdown"])

            fig.add_trace(go.Scatter(x=df.index, y=df["Strategy_Equity"], name="Estrategia",
                                     line=dict(color="#60a5fa", width=2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["BuyHold_Equity"], name="Buy & Hold",
                                     line=dict(color="#94a3b8", width=1, dash="dot")), row=1, col=1)

            # Buy/sell markers
            buys = df[df["Position"] == 1]
            sells = df[df["Position"] == -1]
            if not buys.empty:
                fig.add_trace(go.Scatter(x=buys.index, y=buys["Strategy_Equity"], mode="markers",
                                         name="Compra", marker=dict(color="#34d399", size=8, symbol="triangle-up")), row=1, col=1)
            if not sells.empty:
                fig.add_trace(go.Scatter(x=sells.index, y=sells["Strategy_Equity"], mode="markers",
                                         name="Venta", marker=dict(color="#f87171", size=8, symbol="triangle-down")), row=1, col=1)

            # Drawdown
            equity = df["Strategy_Equity"]
            running_max = equity.cummax()
            drawdown = (equity - running_max) / running_max * 100
            fig.add_trace(go.Scatter(x=df.index, y=drawdown, fill="tozeroy",
                                     fillcolor="rgba(248,113,113,0.15)", line=dict(color="#f87171", width=1),
                                     name="Drawdown"), row=2, col=1)

            fig.update_layout(
                paper_bgcolor="#000000", plot_bgcolor="#0a0a0a",
                font=dict(color="#94a3b8", size=12, family="Inter"),
                height=600, showlegend=True,
                legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a", font=dict(color="#94a3b8")),
                margin=dict(l=16, r=16, t=24, b=16),
            )
            for ax in ["xaxis", "xaxis2", "yaxis", "yaxis2"]:
                fig.update_layout(**{ax: dict(gridcolor="#1a1a1a", linecolor="#1a1a1a", zerolinecolor="#1a1a1a")})

            st.plotly_chart(fig, use_container_width=True)

            # Trade summary
            st.markdown("<div class='sec-title'>Resumen de Operaciones</div>", unsafe_allow_html=True)
            tc1, tc2, tc3 = st.columns(3)
            tc1.markdown(kpi("Señales de Compra", str(metrics["buy_signals"]), "", "green"), unsafe_allow_html=True)
            tc2.markdown(kpi("Señales de Venta", str(metrics["sell_signals"]), "", "red"), unsafe_allow_html=True)
            total_trades = metrics["buy_signals"] + metrics["sell_signals"]
            tc3.markdown(kpi("Total Operaciones", str(total_trades), "", "blue"), unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Error en backtesting: {e}")
