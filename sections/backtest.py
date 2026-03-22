"""
sections/backtest.py - Advanced Backtesting Engine
SMA Crossover, RSI, Bollinger Breakout, Mean Reversion, MACD Crossover
Walk-Forward analysis & Parameter Optimization
"""
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from ui_shared import DARK, dark_layout, fmt, kpi

try:
    from strategies import (run_bollinger, run_mean_reversion, run_macd_crossover,
                            walk_forward, optimize_params)
    HAS_STRATEGIES = True
except ImportError:
    HAS_STRATEGIES = False


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

    total_return_strat = (df["Strategy_Equity"].iloc[-1] - 1) * 100
    total_return_bh = (df["BuyHold_Equity"].iloc[-1] - 1) * 100

    sharpe = (strat_ret.mean() / strat_ret.std() * np.sqrt(252)) if strat_ret.std() > 0 else 0

    equity = df["Strategy_Equity"]
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min() * 100

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
        <p>SMA Crossover · RSI · Bollinger · Mean Reversion · MACD · Walk-Forward · Optimización</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # Config
    strategy_options = ["SMA Crossover", "RSI Oversold/Overbought"]
    if HAS_STRATEGIES:
        strategy_options += ["Bollinger Breakout", "Mean Reversion", "MACD Crossover"]

    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.text_input("Ticker", value="AAPL", placeholder="AAPL").strip().upper()
    with c2:
        period = st.selectbox("Período", ["1y", "2y", "3y", "5y", "10y"], index=1)
    with c3:
        strategy = st.selectbox("Estrategia", strategy_options)

    # Strategy params
    if strategy == "SMA Crossover":
        pc1, pc2 = st.columns(2)
        fast_period = pc1.number_input("SMA Rápida", min_value=5, max_value=100, value=20, step=5)
        slow_period = pc2.number_input("SMA Lenta", min_value=10, max_value=300, value=50, step=10)
    elif strategy == "RSI Oversold/Overbought":
        pc1, pc2, pc3 = st.columns(3)
        rsi_period = pc1.number_input("Período RSI", min_value=5, max_value=30, value=14, step=1)
        oversold = pc2.number_input("Nivel Sobreventa", min_value=10, max_value=40, value=30, step=5)
        overbought = pc3.number_input("Nivel Sobrecompra", min_value=60, max_value=90, value=70, step=5)
    elif strategy == "Bollinger Breakout":
        pc1, pc2 = st.columns(2)
        bb_window = pc1.number_input("Ventana Bollinger", min_value=5, max_value=100, value=20, step=5)
        bb_std = pc2.number_input("Num. Desviaciones", min_value=0.5, max_value=4.0, value=2.0, step=0.5)
    elif strategy == "Mean Reversion":
        pc1, pc2 = st.columns(2)
        mr_window = pc1.number_input("Ventana Media", min_value=5, max_value=100, value=20, step=5)
        mr_threshold = pc2.number_input("Threshold (std)", min_value=0.5, max_value=4.0, value=1.5, step=0.5)
    elif strategy == "MACD Crossover":
        pc1, pc2, pc3 = st.columns(3)
        macd_fast = pc1.number_input("EMA Rápida", min_value=2, max_value=50, value=12, step=1)
        macd_slow = pc2.number_input("EMA Lenta", min_value=10, max_value=100, value=26, step=1)
        macd_signal = pc3.number_input("Señal MACD", min_value=2, max_value=30, value=9, step=1)

    if st.button("Ejecutar Backtest", type="primary", use_container_width=True):
        if not ticker:
            st.warning("Ingresa un ticker.")
            return

        try:
            with st.spinner(f"Descargando datos de {ticker} y ejecutando backtest..."):
                data = yf.download(ticker, period=period, progress=False)
                if data.empty:
                    st.error(f"No se encontraron datos para {ticker}")
                    return

                # Flatten multi-index columns if present
                if hasattr(data.columns, 'levels'):
                    data.columns = data.columns.get_level_values(0)

                if strategy == "SMA Crossover":
                    df = _run_sma_crossover(data, fast=fast_period, slow=slow_period)
                elif strategy == "RSI Oversold/Overbought":
                    df = _run_rsi_strategy(data, period=rsi_period, oversold=oversold, overbought=overbought)
                elif strategy == "Bollinger Breakout":
                    df = run_bollinger(data, window=bb_window, num_std=bb_std)
                elif strategy == "Mean Reversion":
                    df = run_mean_reversion(data, window=mr_window, threshold=mr_threshold)
                elif strategy == "MACD Crossover":
                    df = run_macd_crossover(data, fast=macd_fast, slow=macd_slow, signal=macd_signal)

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

            # ── Export PDF Button ──
            st.markdown("---")
            if st.button("📥 Exportar Backtest PDF", key="bt_export_pdf", use_container_width=True):
                try:
                    from report_generator import generate_backtest_report
                    import file_saver

                    if strategy == "SMA Crossover":
                        strat_name = "SMA Crossover"
                        strat_params = {"SMA Rapida": fast_period, "SMA Lenta": slow_period, "Periodo": period}
                    elif strategy == "RSI Oversold/Overbought":
                        strat_name = "RSI Oversold/Overbought"
                        strat_params = {"Periodo RSI": rsi_period, "Sobreventa": oversold, "Sobrecompra": overbought, "Periodo": period}
                    elif strategy == "Bollinger Breakout":
                        strat_name = "Bollinger Breakout"
                        strat_params = {"Ventana": bb_window, "Num Std": bb_std, "Periodo": period}
                    elif strategy == "Mean Reversion":
                        strat_name = "Mean Reversion"
                        strat_params = {"Ventana": mr_window, "Threshold": mr_threshold, "Periodo": period}
                    elif strategy == "MACD Crossover":
                        strat_name = "MACD Crossover"
                        strat_params = {"Fast": macd_fast, "Slow": macd_slow, "Signal": macd_signal, "Periodo": period}
                    else:
                        strat_name = strategy
                        strat_params = {"Periodo": period}

                    pdf_bytes = generate_backtest_report(
                        ticker=ticker,
                        strategy_name=strat_name,
                        params=strat_params,
                        metrics=metrics,
                    )
                    file_saver.save_or_download(
                        data=pdf_bytes,
                        filename=f"backtest_{ticker}_{strat_name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        label="📥 Descargar Backtest PDF",
                        key="bt_pdf_download",
                    )
                except Exception as pdf_err:
                    st.error(f"Error al generar PDF: {pdf_err}")

            # ══════════════════════════════════════════════════════════
            # WALK-FORWARD ANALYSIS
            # ══════════════════════════════════════════════════════════
            if HAS_STRATEGIES:
                with st.expander("🔬 Análisis Walk-Forward"):
                    try:
                        # Map strategy to function and params
                        if strategy == "SMA Crossover":
                            wf_fn = _run_sma_crossover
                            wf_params = {"fast": fast_period, "slow": slow_period}
                        elif strategy == "RSI Oversold/Overbought":
                            wf_fn = _run_rsi_strategy
                            wf_params = {"period": rsi_period, "oversold": oversold, "overbought": overbought}
                        elif strategy == "Bollinger Breakout":
                            wf_fn = run_bollinger
                            wf_params = {"window": bb_window, "num_std": bb_std}
                        elif strategy == "Mean Reversion":
                            wf_fn = run_mean_reversion
                            wf_params = {"window": mr_window, "threshold": mr_threshold}
                        elif strategy == "MACD Crossover":
                            wf_fn = run_macd_crossover
                            wf_params = {"fast": macd_fast, "slow": macd_slow, "signal": macd_signal}

                        n_splits = st.slider("Número de folds", min_value=3, max_value=10, value=5, key="wf_splits")

                        if st.button("Ejecutar Walk-Forward", key="wf_run"):
                            with st.spinner("Ejecutando análisis walk-forward..."):
                                wf_result = walk_forward(data.copy(), wf_fn, wf_params, n_splits=n_splits)

                            if wf_result.get("error"):
                                st.warning(wf_result["error"])
                            elif wf_result["folds"]:
                                wf_df = pd.DataFrame(wf_result["folds"])

                                # KPIs
                                wk1, wk2, wk3 = st.columns(3)
                                avg_test = wf_result["combined_test_return"]
                                stab = wf_result["stability"]
                                avg_color = "green" if avg_test >= 0 else "red"
                                stab_color = "green" if stab < 10 else "red"
                                wk1.markdown(kpi("Retorno Promedio Test", f"{avg_test:+.1f}%", "", avg_color), unsafe_allow_html=True)
                                wk2.markdown(kpi("Estabilidad (Std)", f"{stab:.1f}%", "menor=mejor", stab_color), unsafe_allow_html=True)
                                n_positive = sum(1 for f in wf_result["folds"] if f["test_return"] > 0)
                                wk3.markdown(kpi("Folds Positivos", f"{n_positive}/{len(wf_result['folds'])}", "", "blue"), unsafe_allow_html=True)

                                # Table
                                st.markdown("##### Rendimiento por Fold")
                                display_df = wf_df[["fold", "train_return", "test_return", "train_sharpe", "test_sharpe"]].copy()
                                display_df.columns = ["Fold", "Train Ret(%)", "Test Ret(%)", "Train Sharpe", "Test Sharpe"]
                                st.dataframe(display_df, use_container_width=True, hide_index=True)

                                # Bar chart: train vs test
                                fig_wf = go.Figure()
                                fig_wf.add_trace(go.Bar(x=wf_df["fold"], y=wf_df["train_return"],
                                                        name="Train", marker_color="#60a5fa"))
                                fig_wf.add_trace(go.Bar(x=wf_df["fold"], y=wf_df["test_return"],
                                                        name="Test", marker_color="#f59e0b"))
                                fig_wf.update_layout(
                                    **DARK, height=350, barmode="group",
                                    title=dict(text="Train vs Test Return por Fold", font=dict(color="#94a3b8", size=14), x=0.5),
                                    xaxis_title="Fold", yaxis_title="Retorno (%)",
                                    legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a")
                                )
                                st.plotly_chart(fig_wf, use_container_width=True)
                            else:
                                st.info("No se pudieron generar folds suficientes con estos datos.")
                    except Exception as wf_err:
                        st.error(f"Error en walk-forward: {wf_err}")

                # ══════════════════════════════════════════════════════════
                # PARAMETER OPTIMIZATION
                # ══════════════════════════════════════════════════════════
                with st.expander("🎯 Optimización de Parámetros"):
                    try:
                        st.caption("Grid search sobre combinaciones de parámetros para encontrar el óptimo.")

                        # Define param grids per strategy
                        if strategy == "SMA Crossover":
                            opt_fn = _run_sma_crossover
                            param_grid = {
                                "fast": [10, 15, 20, 25, 30],
                                "slow": [30, 40, 50, 60, 80],
                            }
                        elif strategy == "RSI Oversold/Overbought":
                            opt_fn = _run_rsi_strategy
                            param_grid = {
                                "period": [10, 14, 20],
                                "oversold": [20, 25, 30, 35],
                                "overbought": [65, 70, 75, 80],
                            }
                        elif strategy == "Bollinger Breakout":
                            opt_fn = run_bollinger
                            param_grid = {
                                "window": [10, 15, 20, 25, 30],
                                "num_std": [1.0, 1.5, 2.0, 2.5, 3.0],
                            }
                        elif strategy == "Mean Reversion":
                            opt_fn = run_mean_reversion
                            param_grid = {
                                "window": [10, 15, 20, 25, 30],
                                "threshold": [1.0, 1.25, 1.5, 2.0, 2.5],
                            }
                        elif strategy == "MACD Crossover":
                            opt_fn = run_macd_crossover
                            param_grid = {
                                "fast": [8, 10, 12, 15],
                                "slow": [20, 26, 30],
                                "signal": [7, 9, 11],
                            }

                        st.markdown(f"**Grid:** {param_grid}")
                        total_combos = 1
                        for v in param_grid.values():
                            total_combos *= len(v)
                        st.caption(f"Total combinaciones: {total_combos}")

                        if st.button("Ejecutar Optimización", key="opt_run"):
                            with st.spinner(f"Probando {total_combos} combinaciones..."):
                                opt_df = optimize_params(data.copy(), opt_fn, param_grid)

                            opt_df = opt_df.dropna(subset=["Return(%)"])
                            if opt_df.empty:
                                st.warning("No se generaron resultados válidos.")
                            else:
                                # Best combo
                                best = opt_df.loc[opt_df["Return(%)"].idxmax()]
                                st.markdown(f"**Mejor combinación:** {dict(best.drop(['Return(%)', 'Sharpe']))} "
                                            f"→ Return: **{best['Return(%)']:+.1f}%**, Sharpe: **{best['Sharpe']:.2f}**")

                                # Show full table sorted
                                st.markdown("##### Resultados (ordenados por retorno)")
                                st.dataframe(
                                    opt_df.sort_values("Return(%)", ascending=False).reset_index(drop=True),
                                    use_container_width=True, hide_index=True
                                )

                                # Heatmap if 2 params
                                param_keys = list(param_grid.keys())
                                if len(param_keys) == 2:
                                    pivot = opt_df.pivot_table(
                                        index=param_keys[0], columns=param_keys[1],
                                        values="Return(%)", aggfunc="mean"
                                    )
                                    fig_hm = px.imshow(
                                        pivot, text_auto=".1f",
                                        color_continuous_scale="RdYlGn",
                                        labels=dict(x=param_keys[1], y=param_keys[0], color="Return(%)"),
                                        aspect="auto"
                                    )
                                    fig_hm.update_layout(
                                        **DARK, height=400,
                                        title=dict(text=f"Heatmap: Return(%) por {param_keys[0]} vs {param_keys[1]}",
                                                   font=dict(color="#94a3b8", size=14), x=0.5),
                                    )
                                    st.plotly_chart(fig_hm, use_container_width=True)
                                elif len(param_keys) >= 3:
                                    # For 3+ params, show bar chart of top 15 combos
                                    top15 = opt_df.nlargest(15, "Return(%)").copy()
                                    top15["Label"] = top15.apply(
                                        lambda r: " | ".join(f"{k}={r[k]}" for k in param_keys), axis=1)
                                    fig_bar = px.bar(top15, x="Return(%)", y="Label", orientation="h",
                                                     color="Sharpe", color_continuous_scale="Viridis",
                                                     text=top15["Return(%)"].apply(lambda x: f"{x:+.1f}%"))
                                    fig_bar.update_layout(
                                        **DARK, height=max(350, len(top15) * 30),
                                        title=dict(text="Top 15 Combinaciones", font=dict(color="#94a3b8", size=14), x=0.5),
                                        yaxis_title="", xaxis_title="Retorno (%)",
                                    )
                                    fig_bar.update_traces(textposition="outside")
                                    st.plotly_chart(fig_bar, use_container_width=True)
                    except Exception as opt_err:
                        st.error(f"Error en optimización: {opt_err}")

        except Exception as e:
            st.error(f"Error en backtesting: {e}")
