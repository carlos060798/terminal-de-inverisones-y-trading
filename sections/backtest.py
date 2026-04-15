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
    from backtest_vectorized import VectorizedEngine
    from strategies import walk_forward, optimize_params
    HAS_STRATEGIES = True
except ImportError:
    HAS_STRATEGIES = False


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Backtest & Simulator</h1>
        <p>SMA · RSI · Bollinger · MACD · Walk-Forward · What-If Simulator</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # config
    tab_bt, tab_sim = st.tabs(["📊 Backtesting Histórico", "🎲 Simulador de Escenarios (What-if)"])
    
    with tab_bt:
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
                    res = VectorizedEngine.run_sma_crossover(data, fast=fast_period, slow=slow_period)
                elif strategy == "RSI Oversold/Overbought":
                    res = VectorizedEngine.run_rsi_strategy(data, period=rsi_period, oversold=oversold, overbought=overbought)
                elif strategy == "Bollinger Breakout":
                    res = VectorizedEngine.run_bollinger(data, window=bb_window, num_std=bb_std)
                elif strategy == "Mean Reversion":
                    res = VectorizedEngine.run_mean_reversion(data, window=mr_window, threshold=mr_threshold)
                elif strategy == "MACD Crossover":
                    res = VectorizedEngine.run_macd_crossover(data, fast=macd_fast, slow=macd_slow, signal=macd_signal)

            metrics = VectorizedEngine.extract_metrics(res, data)
            df = VectorizedEngine.generate_ui_dataframe(res, data)

            # ── Premium UI Layout ──
            st.markdown("""
            <style>
            .bt-container {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 15px;
                margin-top: 20px;
            }
            .bt-card {
                background: rgba(30, 41, 59, 0.4);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
            }
            .bt-label { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
            .bt-value { font-size: 24px; font-weight: 800; color: #ffffff; }
            .bt-delta { font-size: 11px; margin-top: 5px; font-weight: 600; }
            </style>
            """, unsafe_allow_html=True)

            # KPIs
            mk1, mk2, mk3, mk4 = st.columns(4)
            strat_val = metrics['total_return_strat']
            bh_val = metrics['total_return_bh']
            alpha = strat_val - bh_val
            
            with mk1:
                st.markdown(f"<div class='bt-card'><div class='bt-label'>Retorno Estrategia</div><div class='bt-value'>{strat_val:+.1f}%</div></div>", unsafe_allow_html=True)
            with mk2:
                st.markdown(f"<div class='bt-card'><div class='bt-label'>Retorno Buy & Hold</div><div class='bt-value'>{bh_val:+.1f}%</div></div>", unsafe_allow_html=True)
            with mk3:
                st.markdown(f"<div class='bt-card'><div class='bt-label'>Alpha Generado</div><div class='bt-value' style='color:{'#10b981' if alpha>=0 else '#ef4444'}'>{alpha:+.1f}%</div></div>", unsafe_allow_html=True)
            with mk4:
                st.markdown(f"<div class='bt-card'><div class='bt-label'>Max Drawdown</div><div class='bt-value' style='color:#ef4444'>{metrics['max_drawdown']:.1f}%</div></div>", unsafe_allow_html=True)

            # Ratio Section
            st.markdown("<br>", unsafe_allow_html=True)
            rk1, rk2, rk3 = st.columns(3)
            with rk1:
                st.markdown(f"<div class='bt-card'><div class='bt-label'>Sharpe Ratio</div><div class='bt-value' style='color:#60a5fa'>{metrics['sharpe']:.2f}</div></div>", unsafe_allow_html=True)
            with rk2:
                st.markdown(f"<div class='bt-card'><div class='bt-label'>Sortino Ratio</div><div class='bt-value' style='color:#60a5fa'>{metrics.get('sortino', 0):.2f}</div></div>", unsafe_allow_html=True)
            with rk3:
                pf = metrics.get('profit_factor', 0)
                st.markdown(f"<div class='bt-card'><div class='bt-label'>Profit Factor</div><div class='bt-value' style='color:{'#10b981' if pf > 1 else '#f87171'}'>{pf:.2f}</div></div>", unsafe_allow_html=True)

            # Equity curve chart
            st.markdown("<div class='sec-title'>Comparativa de Rendimiento Agregado</div>", unsafe_allow_html=True)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                                row_heights=[0.7, 0.3],
                                subplot_titles=["Curvas de Equidad (Normalizadas)", "Intensidad de Drawdown"])

            fig.add_trace(go.Scatter(x=df.index, y=df["Strategy_Equity"], name="Quantum Strategy",
                                     line=dict(color="#60a5fa", width=3), fill='tozeroy', fillcolor='rgba(96, 165, 250, 0.05)'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["BuyHold_Equity"], name="SPY Benchmark (Proxy)",
                                     line=dict(color="#94a3b8", width=1.5, dash="dot")), row=1, col=1)

            # Buy/sell markers with annotations
            buys = df[df["Position"] == 1]
            sells = df[df["Position"] == -1]
            if not buys.empty:
                fig.add_trace(go.Scatter(x=buys.index, y=buys["Strategy_Equity"], mode="markers",
                                         name="Señal Compra", marker=dict(color="#10b981", size=10, symbol="triangle-up", line=dict(width=1, color="white"))), row=1, col=1)
            if not sells.empty:
                fig.add_trace(go.Scatter(x=sells.index, y=sells["Strategy_Equity"], mode="markers",
                                         name="Señal Venta", marker=dict(color="#ef4444", size=10, symbol="triangle-down", line=dict(width=1, color="white"))), row=1, col=1)

            # Drawdown
            equity = df["Strategy_Equity"]
            running_max = equity.cummax()
            drawdown = (equity - running_max) / running_max * 100
            fig.add_trace(go.Scatter(x=df.index, y=drawdown, fill="tozeroy",
                                     fillcolor="rgba(239, 68, 68, 0.15)", line=dict(color="#ef4444", width=1.5),
                                     name="Drawdown %"), row=2, col=1)

            fig.update_layout(**dark_layout(height=650))
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

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
                            wf_fn = VectorizedEngine.run_sma_crossover
                            wf_params = {"fast": fast_period, "slow": slow_period}
                        elif strategy == "RSI Oversold/Overbought":
                            wf_fn = VectorizedEngine.run_rsi_strategy
                            wf_params = {"period": rsi_period, "oversold": oversold, "overbought": overbought}
                        elif strategy == "Bollinger Breakout":
                            wf_fn = VectorizedEngine.run_bollinger
                            wf_params = {"window": bb_window, "num_std": bb_std}
                        elif strategy == "Mean Reversion":
                            wf_fn = VectorizedEngine.run_mean_reversion
                            wf_params = {"window": mr_window, "threshold": mr_threshold}
                        elif strategy == "MACD Crossover":
                            wf_fn = VectorizedEngine.run_macd_crossover
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
                            opt_fn = VectorizedEngine.run_sma_crossover
                            param_grid = {
                                "fast": [10, 15, 20, 25, 30],
                                "slow": [30, 40, 50, 60, 80],
                            }
                        elif strategy == "RSI Oversold/Overbought":
                            opt_fn = VectorizedEngine.run_rsi_strategy
                            param_grid = {
                                "period": [10, 14, 20],
                                "oversold": [20, 25, 30, 35],
                                "overbought": [65, 70, 75, 80],
                            }
                        elif strategy == "Bollinger Breakout":
                            opt_fn = VectorizedEngine.run_bollinger
                            param_grid = {
                                "window": [10, 15, 20, 25, 30],
                                "num_std": [1.0, 1.5, 2.0, 2.5, 3.0],
                            }
                        elif strategy == "Mean Reversion":
                            opt_fn = VectorizedEngine.run_mean_reversion
                            param_grid = {
                                "window": [10, 15, 20, 25, 30],
                                "threshold": [1.0, 1.25, 1.5, 2.0, 2.5],
                            }
                        elif strategy == "MACD Crossover":
                            opt_fn = VectorizedEngine.run_macd_crossover
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

    # ══════════════════════════════════════════════════════════
    # TAB 2: SCENARIO SIMULATOR
    # ══════════════════════════════════════════════════════════
    with tab_sim:
        st.markdown("<div class='sec-title'>Validador de Tesis: Simulación Probabilística</div>", unsafe_allow_html=True)
        
        sc1, sc2, sc3 = st.columns([1.5, 1, 1])
        s_ticker = sc1.text_input("Ticker para simulación", value=ticker if ticker else "AAPL").upper()
        s_direction = sc2.selectbox("Dirección", ["Compra (Long)", "Venta (Short)"], key="sim_dir")
        s_capital = sc3.number_input("Capital a Riesgo ($)", min_value=100.0, value=1000.0, step=100.0)

        if s_ticker:
            try:
                with st.spinner("Analizando contexto de mercado..."):
                    obj = yf.Ticker(s_ticker)
                    hist_sim = obj.history(period="6mo")
                    if hist_sim.empty:
                        st.warning("No hay datos históricos para este ticker.")
                        return
                    
                    # Technical context for probability
                    last_price = hist_sim["Close"].iloc[-1]
                    # ATR (14)
                    high_low = hist_sim["High"] - hist_sim["Low"]
                    high_close = (hist_sim["High"] - hist_sim["Close"].shift()).abs()
                    low_close = (hist_sim["Low"] - hist_sim["Close"].shift()).abs()
                    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                    atr = tr.rolling(14).mean().iloc[-1]
                    
                    # Trend context (SMA 50/200)
                    sma50 = hist_sim["Close"].rolling(50).mean().iloc[-1]
                    sma200 = hist_sim["Close"].rolling(200).mean().iloc[-1]
                    trend_score = 1.0 if last_price > sma50 > sma200 else (0.5 if last_price > sma50 else 0.0)
                    if "Short" in s_direction: trend_score = 1.0 - trend_score

                st.markdown(f"**Precio Actual:** `${last_price:,.2f}` | **ATR(14):** `${atr:,.2f}`")
                
                sp1, sp2, sp3 = st.columns(3)
                s_entry = sp1.number_input("Entrada ($)", value=float(last_price), step=0.01)
                s_sl = sp2.number_input("Stop Loss ($)", value=float(s_entry - (atr * 1.5)) if "Compra" in s_direction else float(s_entry + (atr * 1.5)), step=0.01)
                s_tp = sp3.number_input("Take Profit ($)", value=float(s_entry + (atr * 3)) if "Compra" in s_direction else float(s_entry - (atr * 3)), step=0.01)

                # Risk/Reward
                risk = abs(s_entry - s_sl)
                reward = abs(s_tp - s_entry)
                rr = reward / risk if risk > 0 else 0
                
                # Probability estimation
                # Base 45% + Trend bonus (20%) + R/R penalty (if RR is too high, prob drops)
                base_prob = 0.45 + (trend_score * 0.20)
                rr_factor = max(0.2, 1.0 - (rr / 10)) # Penalizar R/R > 10
                est_prob = base_prob * rr_factor * 100
                
                st.markdown("---")
                sk1, sk2, sk3 = st.columns(3)
                sk1.markdown(kpi("Risk / Reward", f"1 : {rr:.1f}", f"Risk: ${risk:,.2f}", "blue"), unsafe_allow_html=True)
                sk2.markdown(kpi("Prob. Éxito (Est.)", f"{est_prob:.1f}%", f"Trend: {trend_score*100:.0f}%", "green" if est_prob > 50 else "orange"), unsafe_allow_html=True)
                
                # Expected Value
                ev = (est_prob/100 * reward) - ((1 - est_prob/100) * risk)
                sk3.markdown(kpi("Valor Esperado/Acción", f"${ev:,.2f}", "Prob x Rew - (1-Prob) x Risk", "green" if ev > 0 else "red"), unsafe_allow_html=True)

                # --- PROFIT SIMULATOR ---
                st.markdown("#### Simulación Neta (Comisiones/Slippage)")
                si_cols = st.columns(2)
                slippage = si_cols[0].slider("Slippage (%)", 0.0, 1.0, 0.1, step=0.05)
                comm = si_cols[1].number_input("Comisión por Trade ($)", 0.0, 20.0, 1.5)
                
                shares = s_capital / risk if risk > 0 else 0
                gross_loss = s_capital
                gross_profit = shares * reward
                
                # Adjust for fees/slip
                net_profit = gross_profit * (1 - slippage/100) - comm
                net_loss = gross_loss * (1 + slippage/100) + comm
                
                st.markdown(f"""
                <div style='background:rgba(255,255,255,0.03);padding:20px;border-radius:15px;border:1px solid rgba(255,255,255,0.1);'>
                    <div style='display:flex;justify-content:space-between;margin-bottom:10px;'>
                        <span style='color:#94a3b8;'>Acciones Sugeridas:</span>
                        <span style='font-weight:700;color:#60a5fa;'>{shares:.2f} {s_ticker}</span>
                    </div>
                    <div style='display:flex;justify-content:space-between;margin-bottom:10px;'>
                        <span style='color:#34d399;'>Beneficio Neto si Toca TP:</span>
                        <span style='font-weight:700;color:#34d399;'>+${net_profit:,.2f}</span>
                    </div>
                    <div style='display:flex;justify-content:space-between;'>
                        <span style='color:#f87171;'>Pérdida Neta si Toca SL:</span>
                        <span style='font-weight:700;color:#f87171;'>-${net_loss:,.2f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Visualization of Scenario
                fig_sim = go.Figure()
                fig_sim.add_trace(go.Scatter(x=[-1, 1], y=[s_entry, s_entry], name="Entrada", line=dict(color="#60a5fa", dash="dash", width=1.5)))
                fig_sim.add_trace(go.Scatter(x=[-1.2, 1.2], y=[s_tp, s_tp], name="Take Profit", line=dict(color="#34d399", width=2), fill="tonexty", fillcolor="rgba(52,211,153,0.05)"))
                fig_sim.add_trace(go.Scatter(x=[-1.2, 1.2], y=[s_sl, s_sl], name="Stop Loss", line=dict(color="#f87171", width=2)))
                
                # Simulated current price range
                fig_sim.add_trace(go.Scatter(x=[0], y=[last_price], mode="markers+text", name="Precio Actual", 
                                             text=[f"Actual: ${last_price:,.2f}"], textposition="top right",
                                             marker=dict(color="#e2e8f0", size=10)))

                fig_sim.update_layout(
                    **dark_layout(
                        height=350, showlegend=True, 
                        title=dict(text=f"Proyección Visual de Escenario ({s_ticker})", font=dict(color="#94a3b8", size=13), x=0.5),
                        xaxis=dict(showgrid=False, showticklabels=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                )
                st.plotly_chart(fig_sim, use_container_width=True)

            except Exception as e:
                st.error(f"Error en simulación: {e}")
