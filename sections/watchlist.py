"""
sections/watchlist.py - Watchlist & Portfolio section
Enhanced: RSI, MACD, Benchmark vs S&P500, Dividends, Position Calculator
"""
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import database as db
from ui_shared import DARK, fmt, kpi


def _calc_rsi(series, period=14):
    """Calculate RSI indicator."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _calc_macd(series, fast=12, slow=26, signal=9):
    """Calculate MACD, Signal, and Histogram."""
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal).mean()
    hist = macd - sig
    return macd, sig, hist


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Watchlist & Cartera</h1>
        <p>Precios en tiempo real · RSI & MACD · Benchmark S&P500 · Dividendos</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── TABS ──
    tab_port, tab_chart, tab_bench, tab_div, tab_calc = st.tabs([
        "📊 Cartera", "📈 Análisis Técnico", "🏛️ Benchmark", "💰 Dividendos", "🧮 Calculadora"
    ])

    # ══════════════════════════════════════════════════════════════
    # TAB 1: CARTERA
    # ══════════════════════════════════════════════════════════════
    with tab_port:
        with st.expander("➕  Agregar nueva posición"):
            c1, c2, c3, c4 = st.columns(4)
            new_tick  = c1.text_input("Ticker", placeholder="AAPL")
            new_share = c2.number_input("Acciones", min_value=0.0, step=1.0)
            new_cost  = c3.number_input("Precio promedio ($)", min_value=0.0, step=0.01)
            new_sect  = c4.selectbox("Sector", ["", "Tecnología", "Salud", "Finanzas", "Energía",
                                                 "Consumo", "Industria", "Materiales", "Utilities", "Otro"])
            c5, c6 = st.columns([3, 1])
            new_notes = c5.text_input("Notas")
            with c6:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Agregar ticker"):
                    if new_tick.strip():
                        db.add_ticker(new_tick.strip(), new_share, new_cost, new_sect, new_notes)
                        st.success(f"✅ {new_tick.upper()} agregado.")
                        st.rerun()

        wl = db.get_watchlist()
        if wl.empty:
            st.info("Tu watchlist está vacía. Agrega tickers para comenzar.")
            return

        tickers = wl["ticker"].tolist()
        with st.spinner("📡 Actualizando precios de mercado…"):
            rows = []
            for tk in tickers:
                try:
                    obj  = yf.Ticker(tk)
                    fi   = obj.fast_info
                    hist = obj.history(period="2d")
                    price = fi.last_price or 0
                    prev  = hist["Close"].iloc[-2] if len(hist) >= 2 else price
                    chg   = ((price - prev) / prev * 100) if prev else 0
                    info  = obj.info
                    rows.append({"ticker": tk, "Precio": price, "Cambio %": chg,
                                 "P/E": info.get("trailingPE"), "52W High": info.get("fiftyTwoWeekHigh"),
                                 "52W Low": info.get("fiftyTwoWeekLow"), "Mkt Cap": fi.market_cap})
                except Exception:
                    rows.append({"ticker": tk, "Precio": None, "Cambio %": None,
                                 "P/E": None, "52W High": None, "52W Low": None, "Mkt Cap": None})

        mkt = pd.DataFrame(rows)
        df  = wl.merge(mkt, on="ticker", how="left")
        df["Valor"]  = df["shares"] * df["Precio"]
        df["P&L $"]  = (df["Precio"] - df["avg_cost"]) * df["shares"]
        df["P&L %"]  = ((df["Precio"] - df["avg_cost"]) / df["avg_cost"] * 100).where(df["avg_cost"] > 0)

        total_inv = (df["avg_cost"] * df["shares"]).sum()
        total_val = df["Valor"].sum()
        total_pnl = total_val - total_inv
        total_pct = (total_pnl / total_inv * 100) if total_inv > 0 else 0

        # ── Portfolio KPIs ──
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(kpi("Valor Total", fmt(total_val), f"{len(df)} posiciones", "blue"), unsafe_allow_html=True)
        k2.markdown(kpi("Capital Invertido", fmt(total_inv), "", "purple"), unsafe_allow_html=True)
        pnl_color = "green" if total_pnl >= 0 else "red"
        pnl_sign  = "+" if total_pnl >= 0 else ""
        k3.markdown(kpi("P&L Total", fmt(total_pnl), f"{pnl_sign}{total_pct:.2f}%", pnl_color), unsafe_allow_html=True)
        best_pos = df.loc[df["P&L %"].idxmax(), "ticker"] if not df["P&L %"].isna().all() else "—"
        k4.markdown(kpi("Mejor Posición", best_pos, "", "green"), unsafe_allow_html=True)

        st.markdown("<div class='sec-title'>Tabla de Posiciones</div>", unsafe_allow_html=True)
        tbl = df[["ticker", "sector", "shares", "avg_cost", "Precio", "Cambio %", "P/E", "Valor", "P&L $", "P&L %"]].copy()
        tbl.columns = ["Ticker", "Sector", "Acciones", "Costo Prom.", "Precio", "Cambio %", "P/E", "Valor ($)", "P&L ($)", "P&L %"]

        def clr(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "color:#475569"
            return "color:#34d399" if v >= 0 else "color:#f87171"

        st.dataframe(
            tbl.style.map(clr, subset=["Cambio %", "P&L ($)", "P&L %"])
                     .format({"Costo Prom.": "${:.2f}", "Precio": "${:.2f}", "Cambio %": "{:+.2f}%",
                              "Valor ($)": "${:,.0f}", "P&L ($)": "${:+,.0f}", "P&L %": "{:+.2f}%", "Acciones": "{:.2f}"},
                              na_rep="—"),
            use_container_width=True, hide_index=True
        )

        # ── Charts ──
        st.markdown("<div class='sec-title'>Distribución & Performance</div>", unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            pie_d = df[df["Valor"] > 0]
            if not pie_d.empty:
                fig_p = px.pie(pie_d, names="ticker", values="Valor", hole=0.5,
                               color_discrete_sequence=["#60a5fa", "#34d399", "#a78bfa", "#fbbf24",
                                                        "#f87171", "#38bdf8", "#4ade80", "#e879f9"])
                fig_p.update_traces(textposition="inside", textinfo="percent+label",
                                    textfont=dict(color="white", size=11))
                fig_p.update_layout(**DARK, height=320,
                    title=dict(text="Composición de Cartera", font=dict(color="#94a3b8", size=13), x=0.5),
                    showlegend=False)
                st.plotly_chart(fig_p, use_container_width=True)

        with cc2:
            pnl_d = df[df["shares"] > 0].dropna(subset=["P&L $"])
            if not pnl_d.empty:
                colors_pnl = ["#34d399" if v >= 0 else "#f87171" for v in pnl_d["P&L $"]]
                fig_pnl = go.Figure(go.Bar(
                    x=pnl_d["ticker"], y=pnl_d["P&L $"],
                    marker_color=colors_pnl,
                    text=[f"${v:+,.0f}" for v in pnl_d["P&L $"]],
                    textposition="outside", textfont=dict(color="#94a3b8", size=11),
                ))
                fig_pnl.update_layout(**DARK, height=320,
                    title=dict(text="P&L por Posición", font=dict(color="#94a3b8", size=13), x=0.5),
                    showlegend=False)
                st.plotly_chart(fig_pnl, use_container_width=True)

        # ── Remove ──
        with st.expander("🗑️  Eliminar ticker"):
            del_t = st.selectbox("Ticker a eliminar", [""] + tickers, label_visibility="collapsed")
            if del_t and st.button(f"Eliminar {del_t}"):
                db.remove_ticker(del_t)
                st.success(f"✅ {del_t} eliminado.")
                st.rerun()

    # ══════════════════════════════════════════════════════════════
    # TAB 2: ANÁLISIS TÉCNICO (RSI + MACD + Candlestick)
    # ══════════════════════════════════════════════════════════════
    with tab_chart:
        wl2 = db.get_watchlist()
        if wl2.empty:
            st.info("Agrega tickers a tu watchlist primero.")
            return

        tickers2 = wl2["ticker"].tolist()
        tc1, tc2 = st.columns([2, 1])
        sel = tc1.selectbox("Ticker", tickers2, key="tech_ticker")
        per = tc2.select_slider("Período", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], value="6mo", key="tech_period")

        if sel:
            hd = yf.Ticker(sel).history(period=per)
            if not hd.empty:
                hd["MA20"] = hd["Close"].rolling(20).mean()
                hd["MA50"] = hd["Close"].rolling(50).mean()
                hd["RSI"] = _calc_rsi(hd["Close"])
                hd["MACD"], hd["Signal"], hd["MACD_Hist"] = _calc_macd(hd["Close"])

                # ── KPI Row ──
                last_rsi = hd["RSI"].dropna().iloc[-1] if not hd["RSI"].dropna().empty else None
                last_macd = hd["MACD"].dropna().iloc[-1] if not hd["MACD"].dropna().empty else None
                last_signal = hd["Signal"].dropna().iloc[-1] if not hd["Signal"].dropna().empty else None
                last_price = hd["Close"].iloc[-1]
                last_ma20 = hd["MA20"].dropna().iloc[-1] if not hd["MA20"].dropna().empty else None
                last_ma50 = hd["MA50"].dropna().iloc[-1] if not hd["MA50"].dropna().empty else None

                ik1, ik2, ik3, ik4 = st.columns(4)
                if last_rsi is not None:
                    rsi_status = "SOBRECOMPRA" if last_rsi > 70 else ("SOBREVENTA" if last_rsi < 30 else "NEUTRAL")
                    ik1.markdown(kpi("RSI (14)", f"{last_rsi:.1f}", rsi_status,
                                     "red" if last_rsi > 70 else ("green" if last_rsi < 30 else "blue")), unsafe_allow_html=True)

                if last_macd is not None and last_signal is not None:
                    macd_status = "ALCISTA" if last_macd > last_signal else "BAJISTA"
                    ik2.markdown(kpi("MACD", f"{last_macd:.2f}", macd_status,
                                     "green" if last_macd > last_signal else "red"), unsafe_allow_html=True)

                if last_ma20 is not None and last_ma50 is not None:
                    trend = "ALCISTA" if last_price > last_ma20 > last_ma50 else ("BAJISTA" if last_price < last_ma20 < last_ma50 else "LATERAL")
                    ik3.markdown(kpi("Tendencia", trend, f"MA20: ${last_ma20:.2f}",
                                     "green" if trend == "ALCISTA" else ("red" if trend == "BAJISTA" else "blue")), unsafe_allow_html=True)

                ik4.markdown(kpi("Precio", f"${last_price:.2f}", sel, "blue"), unsafe_allow_html=True)

                # ── Combined Chart: Candlestick + RSI + MACD ──
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                    vertical_spacing=0.03,
                                    row_heights=[0.55, 0.2, 0.25],
                                    subplot_titles=["", "RSI (14)", "MACD"])

                fig.add_trace(go.Candlestick(
                    x=hd.index, open=hd["Open"], high=hd["High"],
                    low=hd["Low"], close=hd["Close"], name=sel,
                    increasing=dict(line=dict(color="#34d399"), fillcolor="#34d399"),
                    decreasing=dict(line=dict(color="#f87171"), fillcolor="#f87171"),
                    showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=hd.index, y=hd["MA20"], name="MA20",
                    line=dict(color="#fbbf24", width=1.2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=hd.index, y=hd["MA50"], name="MA50",
                    line=dict(color="#a78bfa", width=1.2)), row=1, col=1)

                fig.add_trace(go.Scatter(x=hd.index, y=hd["RSI"], name="RSI",
                    line=dict(color="#60a5fa", width=1.5), showlegend=False), row=2, col=1)
                fig.add_hline(y=70, line_dash="dot", line_color="#f87171", line_width=0.8, row=2, col=1)
                fig.add_hline(y=30, line_dash="dot", line_color="#34d399", line_width=0.8, row=2, col=1)
                fig.add_hrect(y0=30, y1=70, fillcolor="rgba(96,165,250,0.05)", line_width=0, row=2, col=1)

                macd_colors = ["#34d399" if v >= 0 else "#f87171" for v in hd["MACD_Hist"].fillna(0)]
                fig.add_trace(go.Bar(x=hd.index, y=hd["MACD_Hist"], name="Histograma",
                    marker_color=macd_colors, showlegend=False), row=3, col=1)
                fig.add_trace(go.Scatter(x=hd.index, y=hd["MACD"], name="MACD",
                    line=dict(color="#60a5fa", width=1.2), showlegend=False), row=3, col=1)
                fig.add_trace(go.Scatter(x=hd.index, y=hd["Signal"], name="Señal",
                    line=dict(color="#fbbf24", width=1.2, dash="dot"), showlegend=False), row=3, col=1)

                fig.update_layout(**DARK, height=650,
                    xaxis_rangeslider_visible=False,
                    legend=dict(bgcolor="#0f1923", bordercolor="#1e2d40", font=dict(size=10)),
                    title=dict(text=f"{sel} — Análisis Técnico ({per})", font=dict(color="#94a3b8", size=14)))
                for annotation in fig['layout']['annotations']:
                    annotation['font'] = dict(color="#64748b", size=11)
                fig.update_yaxes(gridcolor="#1e2d40")
                fig.update_xaxes(gridcolor="#1e2d40")
                st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 3: BENCHMARK vs S&P500
    # ══════════════════════════════════════════════════════════════
    with tab_bench:
        wl3 = db.get_watchlist()
        if wl3.empty:
            st.info("Agrega tickers a tu watchlist primero.")
            return

        tickers3 = wl3["ticker"].tolist()
        bc1, bc2 = st.columns([2, 1])
        bench_tickers = bc1.multiselect("Tickers a comparar", tickers3, default=tickers3[:3] if len(tickers3) >= 3 else tickers3)
        bench_period = bc2.select_slider("Período", ["3mo", "6mo", "1y", "2y", "5y"], value="1y", key="bench_per")

        if bench_tickers and st.button("Comparar con S&P 500", type="primary"):
            with st.spinner("Descargando datos históricos…"):
                all_tickers = bench_tickers + ["^GSPC"]
                fig_bench = go.Figure()
                colors = ["#60a5fa", "#34d399", "#a78bfa", "#fbbf24", "#f87171", "#38bdf8", "#e879f9", "#fb923c"]

                for i, tk in enumerate(all_tickers):
                    try:
                        h = yf.Ticker(tk).history(period=bench_period)["Close"]
                        if not h.empty:
                            normalized = (h / h.iloc[0] - 1) * 100
                            name = "S&P 500" if tk == "^GSPC" else tk
                            line_style = dict(color="#94a3b8", width=2.5, dash="dash") if tk == "^GSPC" else dict(color=colors[i % len(colors)], width=1.8)
                            fig_bench.add_trace(go.Scatter(
                                x=normalized.index, y=normalized,
                                name=name, mode="lines", line=line_style))
                    except Exception:
                        continue

                fig_bench.add_hline(y=0, line_dash="dot", line_color="#475569", line_width=0.5)
                fig_bench.update_layout(**DARK, height=450,
                    title=dict(text=f"Rendimiento vs S&P 500 ({bench_period})", font=dict(color="#94a3b8", size=14), x=0.5),
                    yaxis_title="Retorno (%)",
                    legend=dict(bgcolor="#0f1923", bordercolor="#1e2d40"))
                st.plotly_chart(fig_bench, use_container_width=True)

                # Summary table
                st.markdown("<div class='sec-title'>Resumen de Rendimiento</div>", unsafe_allow_html=True)
                summary_rows = []
                for tk in all_tickers:
                    try:
                        h = yf.Ticker(tk).history(period=bench_period)["Close"]
                        if not h.empty:
                            ret = (h.iloc[-1] / h.iloc[0] - 1) * 100
                            vol = h.pct_change().std() * np.sqrt(252) * 100
                            sharpe = (ret / vol) if vol > 0 else 0
                            max_val = h.cummax()
                            dd = ((h - max_val) / max_val * 100).min()
                            name = "S&P 500" if tk == "^GSPC" else tk
                            summary_rows.append({
                                "Ticker": name, "Retorno %": round(ret, 2),
                                "Volatilidad %": round(vol, 2), "Sharpe": round(sharpe, 2),
                                "Max Drawdown %": round(dd, 2)
                            })
                    except Exception:
                        continue

                if summary_rows:
                    sum_df = pd.DataFrame(summary_rows)
                    st.dataframe(
                        sum_df.style.map(
                            lambda v: "color:#34d399" if isinstance(v, (int, float)) and v > 0 else "color:#f87171",
                            subset=["Retorno %"]
                        ).format({"Retorno %": "{:+.2f}%", "Volatilidad %": "{:.2f}%",
                                  "Sharpe": "{:.2f}", "Max Drawdown %": "{:.2f}%"}),
                        use_container_width=True, hide_index=True
                    )

    # ══════════════════════════════════════════════════════════════
    # TAB 4: DIVIDENDOS
    # ══════════════════════════════════════════════════════════════
    with tab_div:
        wl4 = db.get_watchlist()
        if wl4.empty:
            st.info("Agrega tickers a tu watchlist primero.")
            return

        tickers4 = wl4["ticker"].tolist()
        with st.spinner("Consultando dividendos…"):
            div_rows = []
            for tk in tickers4:
                try:
                    obj = yf.Ticker(tk)
                    info = obj.info
                    divs = obj.dividends
                    annual_div = info.get("dividendRate") or 0
                    div_yield = (info.get("dividendYield") or 0) * 100
                    payout = info.get("payoutRatio")
                    shares_held = wl4.loc[wl4["ticker"] == tk, "shares"].values[0]
                    annual_income = annual_div * shares_held
                    last_divs = divs.tail(4) if not divs.empty else pd.Series(dtype=float)

                    div_rows.append({
                        "Ticker": tk,
                        "Div Anual ($)": annual_div,
                        "Yield %": round(div_yield, 2),
                        "Payout %": round((payout or 0) * 100, 1),
                        "Acciones": shares_held,
                        "Ingreso Anual ($)": round(annual_income, 2),
                        "Últ. Dividendo ($)": round(last_divs.iloc[-1], 4) if not last_divs.empty else 0,
                        "Pagos/Año": len(divs.loc[divs.index.year == divs.index.year.max()]) if not divs.empty else 0,
                    })
                except Exception:
                    div_rows.append({"Ticker": tk, "Div Anual ($)": 0, "Yield %": 0,
                                     "Payout %": 0, "Acciones": 0, "Ingreso Anual ($)": 0,
                                     "Últ. Dividendo ($)": 0, "Pagos/Año": 0})

        div_df = pd.DataFrame(div_rows)
        total_div_income = div_df["Ingreso Anual ($)"].sum()
        avg_yield = div_df[div_df["Yield %"] > 0]["Yield %"].mean() if not div_df[div_df["Yield %"] > 0].empty else 0
        payers = len(div_df[div_df["Div Anual ($)"] > 0])

        dk1, dk2, dk3 = st.columns(3)
        dk1.markdown(kpi("Ingreso por Dividendos", f"${total_div_income:,.2f}", "anual estimado", "green"), unsafe_allow_html=True)
        dk2.markdown(kpi("Yield Promedio", f"{avg_yield:.2f}%", f"{payers}/{len(div_df)} pagan", "blue"), unsafe_allow_html=True)
        dk3.markdown(kpi("Ingreso Mensual", f"${total_div_income/12:,.2f}", "estimado", "purple"), unsafe_allow_html=True)

        st.markdown("<div class='sec-title'>Detalle de Dividendos</div>", unsafe_allow_html=True)
        st.dataframe(
            div_df.style.format({
                "Div Anual ($)": "${:.4f}", "Yield %": "{:.2f}%", "Payout %": "{:.1f}%",
                "Acciones": "{:.0f}", "Ingreso Anual ($)": "${:.2f}",
                "Últ. Dividendo ($)": "${:.4f}", "Pagos/Año": "{:.0f}"
            }),
            use_container_width=True, hide_index=True
        )

        div_payers = div_df[div_df["Ingreso Anual ($)"] > 0]
        if not div_payers.empty:
            dc1, dc2 = st.columns(2)
            with dc1:
                fig_div = go.Figure(go.Bar(
                    x=div_payers["Ticker"], y=div_payers["Ingreso Anual ($)"],
                    marker_color="#34d399",
                    text=[f"${v:.2f}" for v in div_payers["Ingreso Anual ($)"]],
                    textposition="outside", textfont=dict(color="#94a3b8", size=10),
                ))
                fig_div.update_layout(**DARK, height=300,
                    title=dict(text="Ingreso por Dividendo ($)", font=dict(color="#94a3b8", size=13), x=0.5),
                    showlegend=False)
                st.plotly_chart(fig_div, use_container_width=True)
            with dc2:
                fig_yield = go.Figure(go.Bar(
                    x=div_payers["Ticker"], y=div_payers["Yield %"],
                    marker_color=["#34d399" if y > 2 else "#60a5fa" for y in div_payers["Yield %"]],
                    text=[f"{v:.2f}%" for v in div_payers["Yield %"]],
                    textposition="outside", textfont=dict(color="#94a3b8", size=10),
                ))
                fig_yield.add_hline(y=2, line_dash="dot", line_color="#fbbf24", annotation_text="2%")
                fig_yield.update_layout(**DARK, height=300,
                    title=dict(text="Dividend Yield (%)", font=dict(color="#94a3b8", size=13), x=0.5),
                    showlegend=False)
                st.plotly_chart(fig_yield, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 5: CALCULADORA DE POSICIÓN
    # ══════════════════════════════════════════════════════════════
    with tab_calc:
        st.markdown("<div class='sec-title'>Calculadora de Tamaño de Posición</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                    border-radius:12px;padding:16px;margin-bottom:20px;color:#94a3b8;font-size:13px;'>
          Calcula cuántas acciones comprar basándote en tu nivel de riesgo.<br>
          <strong>Regla de oro:</strong> Nunca arriesgar más del 1-2% del capital total por operación.
        </div>""", unsafe_allow_html=True)

        pc1, pc2 = st.columns(2)
        with pc1:
            capital = st.number_input("Capital total ($)", min_value=0.0, value=10000.0, step=1000.0)
            risk_pct = st.number_input("Riesgo por operación (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.5)
            entry_price = st.number_input("Precio de entrada ($)", min_value=0.01, value=100.0, step=1.0)
            stop_loss = st.number_input("Stop Loss ($)", min_value=0.01, value=95.0, step=1.0)

        with pc2:
            if entry_price > 0 and stop_loss > 0 and entry_price != stop_loss:
                risk_amount = capital * (risk_pct / 100)
                risk_per_share = abs(entry_price - stop_loss)
                shares_to_buy = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
                position_size = shares_to_buy * entry_price
                position_pct = (position_size / capital * 100) if capital > 0 else 0

                rr_ratios = [1.5, 2, 3]
                tp_levels = [entry_price + (risk_per_share * rr) for rr in rr_ratios]

                st.markdown(f"""
                <div style='background:linear-gradient(135deg,#0d1f35,#0a1628);border:1px solid #1e3a5f;
                            border-radius:14px;padding:24px;'>
                  <div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px;'>Resultado</div>
                  <div style='display:flex;justify-content:space-between;margin-bottom:12px;'>
                    <span style='color:#94a3b8;'>Riesgo máximo ($):</span>
                    <span style='color:#f87171;font-weight:700;'>${risk_amount:,.2f}</span>
                  </div>
                  <div style='display:flex;justify-content:space-between;margin-bottom:12px;'>
                    <span style='color:#94a3b8;'>Riesgo por acción ($):</span>
                    <span style='color:#fbbf24;font-weight:600;'>${risk_per_share:.2f}</span>
                  </div>
                  <div style='display:flex;justify-content:space-between;margin-bottom:12px;border-top:1px solid #1e3a5f;padding-top:12px;'>
                    <span style='color:#e2e8f0;font-weight:600;'>Acciones a comprar:</span>
                    <span style='color:#60a5fa;font-weight:800;font-size:22px;'>{shares_to_buy}</span>
                  </div>
                  <div style='display:flex;justify-content:space-between;margin-bottom:12px;'>
                    <span style='color:#94a3b8;'>Tamaño posición ($):</span>
                    <span style='color:#a78bfa;font-weight:600;'>${position_size:,.2f}</span>
                  </div>
                  <div style='display:flex;justify-content:space-between;margin-bottom:16px;'>
                    <span style='color:#94a3b8;'>% del capital:</span>
                    <span style='color:#94a3b8;font-weight:600;'>{position_pct:.1f}%</span>
                  </div>
                  <div style='border-top:1px solid #1e3a5f;padding-top:12px;'>
                    <div style='font-size:10px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;'>Take Profit Sugerido</div>
                """, unsafe_allow_html=True)

                for rr, tp in zip(rr_ratios, tp_levels):
                    tp_pnl = (tp - entry_price) * shares_to_buy
                    st.markdown(f"""
                    <div style='display:flex;justify-content:space-between;margin-bottom:6px;'>
                      <span style='color:#94a3b8;font-size:12px;'>R:R {rr}:1 → ${tp:.2f}</span>
                      <span style='color:#34d399;font-size:12px;font-weight:600;'>+${tp_pnl:,.2f}</span>
                    </div>""", unsafe_allow_html=True)

                st.markdown("</div></div>", unsafe_allow_html=True)
            else:
                st.info("Ingresa precio de entrada y stop loss para calcular.")
