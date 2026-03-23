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
from ui_shared import DARK, dark_layout, fmt, kpi

try:
    from pypfopt import EfficientFrontier, risk_models, expected_returns
    HAS_PYPFOPT = True
except ImportError:
    HAS_PYPFOPT = False

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

try:
    from scipy.optimize import minimize as scipy_minimize
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


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

    # ── Portfolio Lists ──
    list_col1, list_col2, list_col3 = st.columns([3, 2, 1])
    with list_col1:
        available_lists = db.get_watchlist_lists()
        options = ['Todas'] + available_lists
        active_list = st.selectbox("📂 Lista activa", options, key="active_list_select")
    with list_col2:
        new_list_name = st.text_input("Nueva lista", key="new_list_input", placeholder="Nombre...")
    with list_col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Crear", key="create_list_btn") and new_list_name:
            st.success(f"Lista '{new_list_name}' creada. Agrega tickers para verla.")

    # Use active_list to filter data throughout
    if active_list == 'Todas':
        watchlist_data = db.get_watchlist()
    else:
        watchlist_data = db.get_watchlist_by_list(active_list)

    # ── TABS ──
    tab_port, tab_chart, tab_bench, tab_div, tab_calc, tab_corr, tab_earn, tab_sim, tab_opt, tab_rebal, tab_charts_multi = st.tabs([
        "📊 Cartera", "📈 Análisis Técnico", "🏛️ Benchmark", "💰 Dividendos", "🧮 Calculadora",
        "🔗 Correlación", "📅 Earnings", "🎲 Simulación", "📐 Optimización", "⚖️ Rebalanceo", "📊 Charts"
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
                        target = active_list if active_list != 'Todas' else 'Principal'
                        db.add_ticker(new_tick.strip(), new_share, new_cost, new_sect, new_notes, target)
                        st.success(f"✅ {new_tick.upper()} agregado a '{target}'.")
                        st.rerun()

        # ── Excel/CSV Import ──
        with st.expander("📥 Importar desde Excel/CSV", expanded=False):
            uploaded_file = st.file_uploader("Seleccionar archivo", type=["xlsx", "csv", "xls"], key="excel_import")
            if uploaded_file:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_import = pd.read_csv(uploaded_file)
                    else:
                        df_import = pd.read_excel(uploaded_file)

                    st.markdown("**Vista previa del archivo:**")
                    st.dataframe(df_import.head(10), use_container_width=True)

                    # Auto-detect columns
                    ticker_candidates = [c for c in df_import.columns if any(k in c.lower() for k in ['ticker', 'symbol', 'símbolo', 'accion', 'stock'])]
                    shares_candidates = [c for c in df_import.columns if any(k in c.lower() for k in ['shares', 'cantidad', 'acciones', 'qty', 'quantity'])]
                    price_candidates = [c for c in df_import.columns if any(k in c.lower() for k in ['price', 'cost', 'precio', 'costo', 'avg'])]
                    sector_candidates = [c for c in df_import.columns if any(k in c.lower() for k in ['sector', 'industry', 'industria'])]

                    all_cols = ['(ninguna)'] + list(df_import.columns)

                    mc1, mc2, mc3, mc4 = st.columns(4)
                    with mc1:
                        ticker_col = st.selectbox("Columna Ticker*", all_cols,
                            index=all_cols.index(ticker_candidates[0]) if ticker_candidates else 0, key="map_ticker")
                    with mc2:
                        shares_col = st.selectbox("Columna Shares", all_cols,
                            index=all_cols.index(shares_candidates[0]) if shares_candidates else 0, key="map_shares")
                    with mc3:
                        price_col = st.selectbox("Columna Precio", all_cols,
                            index=all_cols.index(price_candidates[0]) if price_candidates else 0, key="map_price")
                    with mc4:
                        sector_col = st.selectbox("Columna Sector", all_cols,
                            index=all_cols.index(sector_candidates[0]) if sector_candidates else 0, key="map_sector")

                    target_list = st.selectbox("Importar a lista:", db.get_watchlist_lists(), key="import_target_list")

                    if st.button("🚀 Importar", key="btn_import_excel"):
                        if ticker_col == '(ninguna)':
                            st.error("Selecciona la columna de Ticker")
                        else:
                            imported = 0
                            errors = 0
                            for _, row in df_import.iterrows():
                                try:
                                    ticker_val = str(row[ticker_col]).strip().upper()
                                    if not ticker_val or ticker_val in ('NAN', 'NONE', ''):
                                        continue
                                    try:
                                        shares_val = float(row[shares_col]) if shares_col != '(ninguna)' else 0
                                        if pd.isna(shares_val): shares_val = 0
                                    except (ValueError, TypeError):
                                        shares_val = 0
                                    try:
                                        price_val = float(row[price_col]) if price_col != '(ninguna)' else 0
                                        if pd.isna(price_val): price_val = 0
                                    except (ValueError, TypeError):
                                        price_val = 0
                                    sector_val = str(row[sector_col]).strip() if sector_col != '(ninguna)' and pd.notna(row.get(sector_col)) else ''
                                    db.add_ticker(ticker_val, shares_val, price_val, sector_val, '', target_list)
                                    imported += 1
                                except Exception:
                                    errors += 1
                            st.success(f"✅ {imported} tickers importados a '{target_list}' | {errors} errores")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error leyendo archivo: {e}")

        wl = watchlist_data
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

        # ── Edit Notes ──
        try:
            with st.expander("📝 Editar Notas"):
                note_ticker = st.selectbox(
                    "Selecciona ticker", tickers, key="note_ticker_sel"
                )
                if note_ticker:
                    row_data = wl[wl["ticker"] == note_ticker].iloc[0]
                    current_notes = row_data.get("notes", "") if pd.notna(row_data.get("notes", "")) else ""
                    new_notes = st.text_area(
                        "Notas", value=str(current_notes),
                        height=120, key="note_text_area",
                        placeholder="Escribe tus notas sobre esta posicion..."
                    )
                    if st.button("Guardar Notas", key="save_notes_btn"):
                        try:
                            db.update_ticker(
                                note_ticker,
                                float(row_data.get("shares", 0)),
                                float(row_data.get("avg_cost", 0)),
                                str(row_data.get("sector", "")),
                                new_notes,
                            )
                            st.success(f"Notas guardadas para {note_ticker}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar notas: {e}")
        except Exception as e:
            st.info(f"No se pudo cargar el editor de notas: {e}")

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
                    legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a", font=dict(size=10)),
                    title=dict(text=f"{sel} — Análisis Técnico ({per})", font=dict(color="#94a3b8", size=14)))
                for annotation in fig['layout']['annotations']:
                    annotation['font'] = dict(color="#64748b", size=11)
                fig.update_yaxes(gridcolor="#1a1a1a")
                fig.update_xaxes(gridcolor="#1a1a1a")
                st.plotly_chart(fig, use_container_width=True)

        # ── ADVANCED INDICATORS (pandas-ta) ──
        if HAS_PANDAS_TA:
            with st.expander("📊 Indicadores Técnicos Avanzados"):
                adv_ticker = st.selectbox("Ticker para análisis avanzado", tickers2, key="adv_ta_ticker")
                adv_period = st.selectbox("Período", ["6mo", "1y", "2y"], index=1, key="adv_ta_period")

                adv_indicators = st.multiselect(
                    "Seleccionar indicadores",
                    ["Ichimoku Cloud", "ADX", "Stochastic", "ATR", "OBV"],
                    default=["ADX", "Stochastic"],
                    key="adv_ta_indicators"
                )

                if st.button("Calcular Indicadores Avanzados", type="primary", key="adv_ta_btn"):
                    try:
                        adv_data = yf.download(adv_ticker, period=adv_period, progress=False)
                        if hasattr(adv_data.columns, 'levels'):
                            adv_data.columns = adv_data.columns.get_level_values(0)

                        if adv_data.empty:
                            st.warning(f"No se encontraron datos para {adv_ticker}")
                        else:
                            for indicator in adv_indicators:
                                if indicator == "Ichimoku Cloud":
                                    ichi = adv_data.ta.ichimoku(append=False)
                                    if ichi is not None and len(ichi) == 2:
                                        ichi_df = ichi[0]
                                    elif ichi is not None:
                                        ichi_df = ichi
                                    else:
                                        st.warning("No se pudo calcular Ichimoku")
                                        continue

                                    fig_ichi = go.Figure()
                                    fig_ichi.add_trace(go.Scatter(x=adv_data.index, y=adv_data["Close"],
                                        name="Precio", line=dict(color="#e2e8f0", width=1.5)))

                                    # Find the column names dynamically
                                    cols = ichi_df.columns.tolist()
                                    span_a_col = [c for c in cols if "ISA" in c]
                                    span_b_col = [c for c in cols if "ISB" in c]
                                    tenkan_col = [c for c in cols if "ITS" in c]
                                    kijun_col = [c for c in cols if "IKS" in c]

                                    if tenkan_col:
                                        fig_ichi.add_trace(go.Scatter(x=ichi_df.index, y=ichi_df[tenkan_col[0]],
                                            name="Tenkan-sen", line=dict(color="#60a5fa", width=1)))
                                    if kijun_col:
                                        fig_ichi.add_trace(go.Scatter(x=ichi_df.index, y=ichi_df[kijun_col[0]],
                                            name="Kijun-sen", line=dict(color="#f87171", width=1)))
                                    if span_a_col and span_b_col:
                                        fig_ichi.add_trace(go.Scatter(x=ichi_df.index, y=ichi_df[span_a_col[0]],
                                            name="Senkou A", line=dict(color="#34d399", width=0.5)))
                                        fig_ichi.add_trace(go.Scatter(x=ichi_df.index, y=ichi_df[span_b_col[0]],
                                            name="Senkou B", line=dict(color="#f87171", width=0.5),
                                            fill="tonexty", fillcolor="rgba(52,211,153,0.05)"))

                                    fig_ichi.update_layout(**DARK, height=400,
                                        title=dict(text=f"Ichimoku Cloud — {adv_ticker}", font=dict(color="#94a3b8", size=13), x=0.5),
                                        showlegend=True, legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"))
                                    st.plotly_chart(fig_ichi, use_container_width=True)

                                elif indicator == "ADX":
                                    adx_df = adv_data.ta.adx()
                                    if adx_df is not None and not adx_df.empty:
                                        fig_adx = go.Figure()
                                        adx_cols = adx_df.columns.tolist()
                                        adx_col = [c for c in adx_cols if "ADX" in c and "DM" not in c]
                                        dmp_col = [c for c in adx_cols if "DMP" in c]
                                        dmn_col = [c for c in adx_cols if "DMN" in c]

                                        if adx_col:
                                            fig_adx.add_trace(go.Scatter(x=adx_df.index, y=adx_df[adx_col[0]],
                                                name="ADX", line=dict(color="#a78bfa", width=2)))
                                        if dmp_col:
                                            fig_adx.add_trace(go.Scatter(x=adx_df.index, y=adx_df[dmp_col[0]],
                                                name="+DI", line=dict(color="#34d399", width=1)))
                                        if dmn_col:
                                            fig_adx.add_trace(go.Scatter(x=adx_df.index, y=adx_df[dmn_col[0]],
                                                name="-DI", line=dict(color="#f87171", width=1)))

                                        fig_adx.add_hline(y=25, line_dash="dot", line_color="#fbbf24", line_width=0.8,
                                                          annotation_text="Tendencia fuerte (25)")
                                        fig_adx.update_layout(**DARK, height=300,
                                            title=dict(text=f"ADX — {adv_ticker}", font=dict(color="#94a3b8", size=13), x=0.5),
                                            showlegend=True, legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"))
                                        st.plotly_chart(fig_adx, use_container_width=True)

                                elif indicator == "Stochastic":
                                    stoch = adv_data.ta.stoch()
                                    if stoch is not None and not stoch.empty:
                                        fig_stoch = go.Figure()
                                        stoch_cols = stoch.columns.tolist()
                                        k_col = [c for c in stoch_cols if "STOCHk" in c]
                                        d_col = [c for c in stoch_cols if "STOCHd" in c]

                                        if k_col:
                                            fig_stoch.add_trace(go.Scatter(x=stoch.index, y=stoch[k_col[0]],
                                                name="%K", line=dict(color="#60a5fa", width=1.5)))
                                        if d_col:
                                            fig_stoch.add_trace(go.Scatter(x=stoch.index, y=stoch[d_col[0]],
                                                name="%D", line=dict(color="#fbbf24", width=1)))

                                        fig_stoch.add_hline(y=80, line_dash="dot", line_color="#f87171", line_width=0.8, annotation_text="Sobrecompra")
                                        fig_stoch.add_hline(y=20, line_dash="dot", line_color="#34d399", line_width=0.8, annotation_text="Sobreventa")
                                        fig_stoch.update_layout(**dark_layout(height=300,
                                            title=dict(text=f"Stochastic Oscillator — {adv_ticker}", font=dict(color="#94a3b8", size=13), x=0.5),
                                            showlegend=True, legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"),
                                            yaxis=dict(range=[0, 100])))
                                        st.plotly_chart(fig_stoch, use_container_width=True)

                                elif indicator == "ATR":
                                    atr = adv_data.ta.atr()
                                    if atr is not None and not atr.empty:
                                        fig_atr = go.Figure()
                                        fig_atr.add_trace(go.Scatter(x=atr.index, y=atr,
                                            name="ATR", line=dict(color="#fbbf24", width=1.5),
                                            fill="tozeroy", fillcolor="rgba(251,191,36,0.08)"))
                                        fig_atr.update_layout(**DARK, height=280,
                                            title=dict(text=f"ATR (Average True Range) — {adv_ticker}", font=dict(color="#94a3b8", size=13), x=0.5),
                                            showlegend=False)
                                        st.plotly_chart(fig_atr, use_container_width=True)

                                elif indicator == "OBV":
                                    obv = adv_data.ta.obv()
                                    if obv is not None and not obv.empty:
                                        fig_obv = go.Figure()
                                        fig_obv.add_trace(go.Scatter(x=obv.index, y=obv,
                                            name="OBV", line=dict(color="#a78bfa", width=1.5),
                                            fill="tozeroy", fillcolor="rgba(167,139,250,0.08)"))
                                        fig_obv.update_layout(**DARK, height=280,
                                            title=dict(text=f"OBV (On Balance Volume) — {adv_ticker}", font=dict(color="#94a3b8", size=13), x=0.5),
                                            showlegend=False)
                                        st.plotly_chart(fig_obv, use_container_width=True)

                    except Exception as e:
                        st.error(f"Error calculando indicadores: {e}")

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
                    legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"))
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

        # ── DIVIDEND ENHANCEMENTS ──────────────────────────────────────
        try:
            st.markdown("<div class='sec-title'>Historial de Dividendos & Proyecciones</div>", unsafe_allow_html=True)

            # Dividend History Chart per ticker
            div_ticker_sel = st.selectbox(
                "Selecciona ticker para historial de dividendos",
                tickers4,
                key="div_hist_ticker",
            )

            if div_ticker_sel:
                obj_div = yf.Ticker(div_ticker_sel)
                divs_hist = obj_div.dividends

                if not divs_hist.empty and len(divs_hist) > 0:
                    # Bar chart of dividend history
                    fig_div_hist = go.Figure(go.Bar(
                        x=divs_hist.index,
                        y=divs_hist.values,
                        marker_color="#34d399",
                        text=[f"${v:.4f}" for v in divs_hist.values],
                        textposition="outside",
                        textfont=dict(color="#94a3b8", size=9),
                    ))
                    fig_div_hist.update_layout(
                        **DARK, height=350,
                        title=dict(
                            text=f"Historial de Dividendos — {div_ticker_sel}",
                            font=dict(color="#94a3b8", size=13), x=0.5,
                        ),
                        xaxis_title="Fecha",
                        yaxis_title="Dividendo ($)",
                        showlegend=False,
                    )
                    st.plotly_chart(fig_div_hist, use_container_width=True)

                    # Dividend Growth Rate (CAGR)
                    if len(divs_hist) >= 2:
                        # Group by year and sum annual dividends
                        annual_divs = divs_hist.groupby(divs_hist.index.year).sum()
                        if len(annual_divs) >= 2:
                            first_year_div = annual_divs.iloc[0]
                            last_year_div = annual_divs.iloc[-1]
                            n_years = len(annual_divs) - 1
                            if first_year_div > 0 and last_year_div > 0 and n_years > 0:
                                cagr = ((last_year_div / first_year_div) ** (1 / n_years) - 1) * 100
                                st.markdown(
                                    kpi("CAGR Dividendos", f"{cagr:+.2f}%",
                                        f"{n_years} anos ({annual_divs.index[0]}-{annual_divs.index[-1]})",
                                        "green" if cagr > 0 else "red"),
                                    unsafe_allow_html=True,
                                )
                else:
                    st.info(f"{div_ticker_sel} no tiene historial de dividendos.")

            # Projected Annual Income
            st.markdown("<div class='sec-title'>Ingreso Anual Proyectado por Dividendos</div>", unsafe_allow_html=True)
            proj_rows = []
            for tk in tickers4:
                try:
                    obj_p = yf.Ticker(tk)
                    info_p = obj_p.info
                    div_rate = info_p.get("dividendRate") or 0
                    shares_held = wl4.loc[wl4["ticker"] == tk, "shares"].values[0]
                    proj_income = div_rate * shares_held
                    if proj_income > 0:
                        proj_rows.append({
                            "Ticker": tk,
                            "Div Rate ($)": round(div_rate, 4),
                            "Acciones": shares_held,
                            "Ingreso Anual ($)": round(proj_income, 2),
                            "Ingreso Mensual ($)": round(proj_income / 12, 2),
                        })
                except Exception:
                    pass

            if proj_rows:
                proj_df = pd.DataFrame(proj_rows)
                total_proj = proj_df["Ingreso Anual ($)"].sum()
                pj1, pj2 = st.columns(2)
                pj1.markdown(kpi("Ingreso Anual Proyectado", f"${total_proj:,.2f}", "basado en div rate actual", "green"), unsafe_allow_html=True)
                pj2.markdown(kpi("Ingreso Mensual Proyectado", f"${total_proj/12:,.2f}", "", "blue"), unsafe_allow_html=True)
                st.dataframe(
                    proj_df.style.format({
                        "Div Rate ($)": "${:.4f}",
                        "Acciones": "{:.0f}",
                        "Ingreso Anual ($)": "${:.2f}",
                        "Ingreso Mensual ($)": "${:.2f}",
                    }),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("Ninguna posicion tiene dividendos proyectados.")

            # Ex-Dividend Calendar
            st.markdown("<div class='sec-title'>Calendario Ex-Dividendo</div>", unsafe_allow_html=True)
            exdiv_rows = []
            for tk in tickers4:
                try:
                    obj_ex = yf.Ticker(tk)
                    info_ex = obj_ex.info
                    ex_date = info_ex.get("exDividendDate")
                    if ex_date:
                        from datetime import datetime
                        if isinstance(ex_date, (int, float)):
                            ex_date_str = datetime.fromtimestamp(ex_date).strftime("%Y-%m-%d")
                        else:
                            ex_date_str = str(ex_date)
                        div_amount = info_ex.get("dividendRate") or info_ex.get("lastDividendValue") or 0
                        exdiv_rows.append({
                            "Ticker": tk,
                            "Fecha Ex-Dividendo": ex_date_str,
                            "Dividendo ($)": round(div_amount, 4) if div_amount else "N/A",
                            "Yield %": round((info_ex.get("dividendYield") or 0) * 100, 2),
                        })
                except Exception:
                    pass

            if exdiv_rows:
                exdiv_df = pd.DataFrame(exdiv_rows)
                exdiv_df = exdiv_df.sort_values("Fecha Ex-Dividendo")
                st.dataframe(exdiv_df, use_container_width=True, hide_index=True)
            else:
                st.info("No se encontraron fechas ex-dividendo para los tickers en tu watchlist.")

        except Exception as e:
            st.error(f"Error en enhancements de dividendos: {e}")

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

    # ══════════════════════════════════════════════════════════════
    # TAB 6: CORRELACIÓN
    # ══════════════════════════════════════════════════════════════
    with tab_corr:
        try:
            wl_corr = db.get_watchlist()
            if wl_corr.empty:
                st.info("Agrega tickers a tu watchlist primero.")
            else:
                tickers_corr = wl_corr["ticker"].tolist()
                if len(tickers_corr) < 2:
                    st.warning("Se necesitan al menos 2 tickers para calcular la matriz de correlación.")
                else:
                    with st.spinner("Descargando datos para correlación…"):
                        prices_corr = yf.download(tickers_corr, period="1y", progress=False)["Close"]
                        if isinstance(prices_corr, pd.Series):
                            prices_corr = prices_corr.to_frame(tickers_corr[0])
                        corr = prices_corr.pct_change().dropna().corr()

                    if corr.empty:
                        st.warning("No se pudieron obtener datos suficientes para la correlación.")
                    else:
                        st.markdown("<div class='sec-title'>Matriz de Correlación (1 año)</div>", unsafe_allow_html=True)
                        fig_corr = px.imshow(
                            corr,
                            text_auto=".2f",
                            color_continuous_scale=["#f87171", "#000000", "#34d399"],
                            aspect="auto",
                        )
                        fig_corr.update_layout(**DARK, height=400,
                            title=dict(text="Correlación de Retornos Diarios", font=dict(color="#94a3b8", size=13), x=0.5))
                        st.plotly_chart(fig_corr, use_container_width=True)

                        st.markdown("""
                        <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                                    border-radius:12px;padding:14px;color:#94a3b8;font-size:12px;'>
                          <strong>Interpretación:</strong> Valores cercanos a <span style='color:#34d399'>+1.0</span> indican alta correlación positiva.
                          Valores cercanos a <span style='color:#f87171'>-1.0</span> indican correlación inversa (bueno para diversificación).
                          Valores cercanos a <span style='color:#64748b'>0.0</span> indican poca relación.
                        </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error al calcular correlación: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 7: EARNINGS CALENDAR
    # ══════════════════════════════════════════════════════════════
    with tab_earn:
        try:
            wl_earn = db.get_watchlist()
            if wl_earn.empty:
                st.info("Agrega tickers a tu watchlist primero.")
            else:
                tickers_earn = wl_earn["ticker"].tolist()
                st.markdown("<div class='sec-title'>Calendario de Earnings</div>", unsafe_allow_html=True)

                with st.spinner("Consultando fechas de earnings…"):
                    earnings_data = []
                    for t in tickers_earn:
                        try:
                            cal = yf.Ticker(t).calendar
                            if cal is not None:
                                if isinstance(cal, dict):
                                    ed_list = cal.get("Earnings Date", [])
                                    ed = ed_list[0] if ed_list else None
                                elif isinstance(cal, pd.DataFrame) and not cal.empty:
                                    ed = cal.iloc[0, 0] if len(cal) > 0 else None
                                else:
                                    ed = None
                                if ed:
                                    earnings_data.append({"Ticker": t, "Fecha Earnings": str(ed)})
                        except Exception:
                            pass

                if earnings_data:
                    earn_df = pd.DataFrame(earnings_data)
                    earn_df = earn_df.sort_values("Fecha Earnings")

                    # KPIs
                    ek1, ek2 = st.columns(2)
                    ek1.markdown(kpi("Tickers con Earnings", str(len(earn_df)), f"de {len(tickers_earn)} en watchlist", "blue"), unsafe_allow_html=True)
                    next_earn = earn_df.iloc[0]
                    ek2.markdown(kpi("Próximo Earnings", next_earn["Ticker"], next_earn["Fecha Earnings"], "purple"), unsafe_allow_html=True)

                    st.dataframe(earn_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No se encontraron fechas de earnings próximas para los tickers en tu watchlist.")
        except Exception as e:
            st.error(f"Error al consultar earnings: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 8: MONTE CARLO SIMULATION
    # ══════════════════════════════════════════════════════════════
    with tab_sim:
        try:
            wl_sim = db.get_watchlist()
            if wl_sim.empty:
                st.info("Agrega tickers a tu watchlist primero.")
            else:
                tickers_sim = wl_sim["ticker"].tolist()
                if len(tickers_sim) < 1:
                    st.warning("Se necesita al menos 1 ticker para la simulación.")
                else:
                    st.markdown("<div class='sec-title'>Monte Carlo — Simulación de Portafolio</div>", unsafe_allow_html=True)
                    st.markdown("""
                    <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                                border-radius:12px;padding:14px;margin-bottom:16px;color:#94a3b8;font-size:12px;'>
                      Proyección a 1 año con 1000 simulaciones usando retornos diarios históricos (pesos iguales).
                      Basado en distribución normal de retornos de los últimos 2 años.
                    </div>""", unsafe_allow_html=True)

                    if st.button("Ejecutar Simulación Monte Carlo", type="primary", key="mc_btn"):
                        with st.spinner("Descargando datos y ejecutando 1000 simulaciones…"):
                            prices_sim = yf.download(tickers_sim, period="2y", progress=False)["Close"]
                            if isinstance(prices_sim, pd.Series):
                                prices_sim = prices_sim.to_frame(tickers_sim[0])
                            returns_sim = prices_sim.pct_change().dropna()

                            # Equal weight portfolio
                            port_returns = returns_sim.mean(axis=1)
                            mu = port_returns.mean()
                            sigma = port_returns.std()

                            simulations = 1000
                            days = 252
                            sim_results = np.zeros((days, simulations))
                            for i in range(simulations):
                                daily_rets = np.random.normal(mu, sigma, days)
                                sim_results[:, i] = (1 + daily_rets).cumprod()

                        # Plot percentile bands
                        fig_mc = go.Figure()
                        percentiles = [
                            (5,  "#f87171", "P5 (Peor caso)"),
                            (25, "#fbbf24", "P25"),
                            (50, "#60a5fa", "Mediana"),
                            (75, "#fbbf24", "P75"),
                            (95, "#34d399", "P95 (Mejor caso)"),
                        ]
                        for pct, color, name in percentiles:
                            vals = np.percentile(sim_results, pct, axis=1)
                            fig_mc.add_trace(go.Scatter(
                                x=list(range(days)), y=vals,
                                name=name, line=dict(color=color, width=2 if pct == 50 else 1),
                            ))

                        # Add shaded area between P25 and P75
                        p25_vals = np.percentile(sim_results, 25, axis=1)
                        p75_vals = np.percentile(sim_results, 75, axis=1)
                        fig_mc.add_trace(go.Scatter(
                            x=list(range(days)) + list(range(days))[::-1],
                            y=list(p75_vals) + list(p25_vals)[::-1],
                            fill="toself", fillcolor="rgba(96,165,250,0.08)",
                            line=dict(color="rgba(0,0,0,0)"), showlegend=False,
                        ))

                        fig_mc.add_hline(y=1.0, line_dash="dot", line_color="#475569", line_width=0.8,
                                         annotation_text="Inicio", annotation_font_color="#64748b")
                        fig_mc.update_layout(**DARK, height=450,
                            title=dict(text="Monte Carlo — 1000 simulaciones (1 año)", font=dict(color="#94a3b8", size=14), x=0.5),
                            xaxis_title="Días de trading",
                            yaxis_title="Valor relativo ($1 invertido)",
                            legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"))
                        st.plotly_chart(fig_mc, use_container_width=True)

                        # Summary stats
                        final_vals = sim_results[-1, :]
                        sk1, sk2, sk3, sk4 = st.columns(4)
                        median_ret = (np.median(final_vals) - 1) * 100
                        p5_ret = (np.percentile(final_vals, 5) - 1) * 100
                        p95_ret = (np.percentile(final_vals, 95) - 1) * 100
                        prob_profit = (final_vals > 1).sum() / simulations * 100

                        sk1.markdown(kpi("Retorno Mediano", f"{median_ret:+.1f}%", "1 año", "blue"), unsafe_allow_html=True)
                        sk2.markdown(kpi("Peor Escenario (P5)", f"{p5_ret:+.1f}%", "", "red"), unsafe_allow_html=True)
                        sk3.markdown(kpi("Mejor Escenario (P95)", f"{p95_ret:+.1f}%", "", "green"), unsafe_allow_html=True)
                        sk4.markdown(kpi("Prob. Ganancia", f"{prob_profit:.0f}%", f"de {simulations} sims", "purple"), unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error en simulación Monte Carlo: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 9: OPTIMIZACIÓN (Efficient Frontier)
    # ══════════════════════════════════════════════════════════════
    with tab_opt:
        try:
            rows = db.get_watchlist()
            if rows.empty:
                st.info("Agrega al menos 2 tickers a tu watchlist para optimizar la cartera.")
            else:
                tickers = sorted(set(rows["ticker"].tolist()))
                if len(tickers) < 2:
                    st.info("Se necesitan al menos 2 tickers para la optimización de cartera.")
                else:
                    opt_method = st.selectbox("Método", ["Frontera Eficiente", "Risk Parity"], key="opt_method")

                    if opt_method == "Frontera Eficiente":
                        # ── Existing Efficient Frontier code ──
                        if not HAS_PYPFOPT:
                            st.warning("Instala `pypfopt` para usar esta sección: `pip install pyportfolioopt`")
                        else:
                            st.subheader("Frontera Eficiente — Optimización de Cartera")
                            with st.spinner("Descargando precios (2 años)..."):
                                prices = yf.download(tickers, period="2y", auto_adjust=True)["Close"]
                                if isinstance(prices, pd.Series):
                                    prices = prices.to_frame()
                                prices = prices.dropna(axis=1, how="all").dropna()

                            valid_tickers = list(prices.columns)
                            if len(valid_tickers) < 2:
                                st.warning("No se pudieron obtener datos suficientes para al menos 2 tickers.")
                            else:
                                mu = expected_returns.mean_historical_return(prices)
                                S = risk_models.sample_cov(prices)

                                ef_sharpe = EfficientFrontier(mu, S)
                                ef_sharpe.max_sharpe()
                                w_sharpe = ef_sharpe.clean_weights()
                                perf_sharpe = ef_sharpe.portfolio_performance(verbose=False)

                                ef_minvol = EfficientFrontier(mu, S)
                                ef_minvol.min_volatility()
                                w_minvol = ef_minvol.clean_weights()
                                perf_minvol = ef_minvol.portfolio_performance(verbose=False)

                                k1, k2, k3 = st.columns(3)
                                k1.markdown(kpi("Retorno Esperado", f"{perf_sharpe[0]*100:.1f}%", "Max Sharpe", "green"), unsafe_allow_html=True)
                                k2.markdown(kpi("Volatilidad", f"{perf_sharpe[1]*100:.1f}%", "anualizada", "red"), unsafe_allow_html=True)
                                k3.markdown(kpi("Sharpe Ratio", f"{perf_sharpe[2]:.2f}", "óptimo", "blue"), unsafe_allow_html=True)

                                n_assets = len(valid_tickers)
                                n_portfolios = 5000
                                results = np.zeros((n_portfolios, 3))
                                mu_arr = mu.values
                                S_arr = S.values

                                np.random.seed(42)
                                for i in range(n_portfolios):
                                    w = np.random.dirichlet(np.ones(n_assets))
                                    p_ret = np.dot(w, mu_arr)
                                    p_vol = np.sqrt(np.dot(w.T, np.dot(S_arr, w)))
                                    results[i, 0] = p_vol
                                    results[i, 1] = p_ret
                                    results[i, 2] = (p_ret - 0.02) / p_vol

                                fig_ef = go.Figure()
                                fig_ef.add_trace(go.Scatter(
                                    x=results[:, 0] * 100, y=results[:, 1] * 100,
                                    mode="markers",
                                    marker=dict(size=3, color=results[:, 2], colorscale="Viridis",
                                                showscale=True, colorbar=dict(title="Sharpe")),
                                    name="Portafolios aleatorios",
                                    hovertemplate="Vol: %{x:.1f}%<br>Ret: %{y:.1f}%<extra></extra>"
                                ))
                                fig_ef.add_trace(go.Scatter(
                                    x=[perf_sharpe[1] * 100], y=[perf_sharpe[0] * 100],
                                    mode="markers", name="Max Sharpe",
                                    marker=dict(symbol="star", size=18, color="#22c55e", line=dict(width=1, color="white"))
                                ))
                                fig_ef.add_trace(go.Scatter(
                                    x=[perf_minvol[1] * 100], y=[perf_minvol[0] * 100],
                                    mode="markers", name="Min Volatilidad",
                                    marker=dict(symbol="star", size=18, color="#3b82f6", line=dict(width=1, color="white"))
                                ))
                                fig_ef.update_layout(
                                    **DARK, height=500,
                                    title=dict(text="Frontera Eficiente — 5000 portafolios simulados",
                                               font=dict(color="#94a3b8", size=14), x=0.5),
                                    xaxis_title="Volatilidad (%)",
                                    yaxis_title="Retorno Esperado (%)",
                                    legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a")
                                )
                                st.plotly_chart(fig_ef, use_container_width=True)

                                st.markdown("#### Asignación Óptima (Max Sharpe)")
                                alloc_df = pd.DataFrame({
                                    "Ticker": list(w_sharpe.keys()),
                                    "Peso": [v * 100 for v in w_sharpe.values()]
                                })
                                alloc_df = alloc_df[alloc_df["Peso"] > 0.01].sort_values("Peso", ascending=True)

                                fig_alloc = px.bar(alloc_df, x="Peso", y="Ticker", orientation="h",
                                                   text=alloc_df["Peso"].apply(lambda x: f"{x:.1f}%"),
                                                   color="Peso", color_continuous_scale="Viridis")
                                fig_alloc.update_layout(
                                    **DARK, height=max(300, len(alloc_df) * 35),
                                    xaxis_title="Peso (%)", yaxis_title="",
                                    coloraxis_showscale=False
                                )
                                fig_alloc.update_traces(textposition="outside")
                                st.plotly_chart(fig_alloc, use_container_width=True)

                                with st.expander("Ver cartera de Mínima Volatilidad"):
                                    mk1, mk2, mk3 = st.columns(3)
                                    mk1.markdown(kpi("Retorno Esperado", f"{perf_minvol[0]*100:.1f}%", "Min Vol", "green"), unsafe_allow_html=True)
                                    mk2.markdown(kpi("Volatilidad", f"{perf_minvol[1]*100:.1f}%", "anualizada", "red"), unsafe_allow_html=True)
                                    mk3.markdown(kpi("Sharpe Ratio", f"{perf_minvol[2]:.2f}", "", "blue"), unsafe_allow_html=True)

                                    alloc_mv = pd.DataFrame({
                                        "Ticker": list(w_minvol.keys()),
                                        "Peso (%)": [round(v * 100, 2) for v in w_minvol.values()]
                                    })
                                    alloc_mv = alloc_mv[alloc_mv["Peso (%)"] > 0.01].sort_values("Peso (%)", ascending=False)
                                    st.dataframe(alloc_mv, use_container_width=True, hide_index=True)

                    elif opt_method == "Risk Parity":
                        # ── Risk Parity: Equal Risk Contribution ──
                        if not HAS_SCIPY:
                            st.warning("Instala `scipy` para usar Risk Parity: `pip install scipy`")
                        else:
                            st.subheader("Risk Parity — Contribución Igual al Riesgo")
                            st.markdown("""
                            <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                                        border-radius:12px;padding:14px;margin-bottom:16px;color:#94a3b8;font-size:12px;'>
                              <strong>Risk Parity</strong> asigna pesos de modo que cada activo contribuya
                              la misma proporción al riesgo total del portafolio.
                              Es robusto y no depende de estimaciones de retorno esperado.
                            </div>""", unsafe_allow_html=True)

                            with st.spinner("Descargando precios (2 años)..."):
                                prices_rp = yf.download(tickers, period="2y", auto_adjust=True)["Close"]
                                if isinstance(prices_rp, pd.Series):
                                    prices_rp = prices_rp.to_frame()
                                prices_rp = prices_rp.dropna(axis=1, how="all").dropna()

                            valid_tickers_rp = list(prices_rp.columns)
                            if len(valid_tickers_rp) < 2:
                                st.warning("No se pudieron obtener datos suficientes para al menos 2 tickers.")
                            else:
                                returns_rp = prices_rp.pct_change().dropna()
                                cov_matrix = returns_rp.cov().values * 252  # annualized
                                n_assets_rp = len(valid_tickers_rp)

                                # Risk parity objective: minimize sum of (RC_i - RC_target)^2
                                def _risk_contrib(w, cov):
                                    port_vol = np.sqrt(w @ cov @ w)
                                    marginal = cov @ w
                                    rc = w * marginal / port_vol
                                    return rc

                                def _risk_parity_obj(w, cov):
                                    rc = _risk_contrib(w, cov)
                                    target = np.ones(len(w)) / len(w)
                                    rc_pct = rc / rc.sum()
                                    return np.sum((rc_pct - target) ** 2)

                                # Optimization
                                x0 = np.ones(n_assets_rp) / n_assets_rp
                                bounds = tuple((0.01, 1.0) for _ in range(n_assets_rp))
                                constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

                                result_rp = scipy_minimize(
                                    _risk_parity_obj, x0, args=(cov_matrix,),
                                    method="SLSQP", bounds=bounds, constraints=constraints,
                                    options={"maxiter": 1000, "ftol": 1e-12}
                                )

                                if not result_rp.success:
                                    st.warning(f"La optimización no convergió completamente: {result_rp.message}")

                                w_rp = result_rp.x / result_rp.x.sum()  # normalize

                                # Portfolio metrics
                                mu_rp = returns_rp.mean().values * 252
                                port_ret_rp = np.dot(w_rp, mu_rp) * 100
                                port_vol_rp = np.sqrt(w_rp @ cov_matrix @ w_rp) * 100
                                port_sharpe_rp = (port_ret_rp - 2.0) / port_vol_rp if port_vol_rp > 0 else 0

                                # Equal-weight portfolio for comparison
                                w_eq = np.ones(n_assets_rp) / n_assets_rp
                                eq_ret = np.dot(w_eq, mu_rp) * 100
                                eq_vol = np.sqrt(w_eq @ cov_matrix @ w_eq) * 100
                                eq_sharpe = (eq_ret - 2.0) / eq_vol if eq_vol > 0 else 0

                                # KPIs
                                rk1, rk2, rk3 = st.columns(3)
                                rk1.markdown(kpi("Retorno Esperado", f"{port_ret_rp:.1f}%", "Risk Parity", "green"), unsafe_allow_html=True)
                                rk2.markdown(kpi("Volatilidad", f"{port_vol_rp:.1f}%", "anualizada", "red"), unsafe_allow_html=True)
                                rk3.markdown(kpi("Sharpe Ratio", f"{port_sharpe_rp:.2f}", "rf=2%", "blue"), unsafe_allow_html=True)

                                # Weights bar chart
                                rp_alloc = pd.DataFrame({
                                    "Ticker": valid_tickers_rp,
                                    "Peso": w_rp * 100
                                }).sort_values("Peso", ascending=True)

                                fig_rp = px.bar(rp_alloc, x="Peso", y="Ticker", orientation="h",
                                                text=rp_alloc["Peso"].apply(lambda x: f"{x:.1f}%"),
                                                color="Peso", color_continuous_scale="Viridis")
                                fig_rp.update_layout(
                                    **DARK, height=max(300, n_assets_rp * 35),
                                    title=dict(text="Asignación Risk Parity", font=dict(color="#94a3b8", size=14), x=0.5),
                                    xaxis_title="Peso (%)", yaxis_title="",
                                    coloraxis_showscale=False,
                                )
                                fig_rp.update_traces(textposition="outside")
                                st.plotly_chart(fig_rp, use_container_width=True)

                                # Risk contribution chart
                                rc_vals = _risk_contrib(w_rp, cov_matrix)
                                rc_pct = rc_vals / rc_vals.sum() * 100

                                rc_df = pd.DataFrame({
                                    "Ticker": valid_tickers_rp,
                                    "Contribución al Riesgo (%)": rc_pct
                                }).sort_values("Contribución al Riesgo (%)", ascending=True)

                                fig_rc = px.bar(rc_df, x="Contribución al Riesgo (%)", y="Ticker", orientation="h",
                                                text=rc_df["Contribución al Riesgo (%)"].apply(lambda x: f"{x:.1f}%"),
                                                color_discrete_sequence=["#60a5fa"])
                                fig_rc.update_layout(
                                    **DARK, height=max(300, n_assets_rp * 35),
                                    title=dict(text="Contribución al Riesgo por Activo (objetivo: iguales)",
                                               font=dict(color="#94a3b8", size=14), x=0.5),
                                    xaxis_title="Contribución (%)", yaxis_title="",
                                )
                                fig_rc.update_traces(textposition="outside")
                                st.plotly_chart(fig_rc, use_container_width=True)

                                # Comparison table: Risk Parity vs Equal Weight
                                st.markdown("#### Comparación: Risk Parity vs Equal Weight")
                                comp_df = pd.DataFrame({
                                    "Métrica": ["Retorno Esperado", "Volatilidad", "Sharpe Ratio"],
                                    "Risk Parity": [f"{port_ret_rp:.1f}%", f"{port_vol_rp:.1f}%", f"{port_sharpe_rp:.2f}"],
                                    "Equal Weight": [f"{eq_ret:.1f}%", f"{eq_vol:.1f}%", f"{eq_sharpe:.2f}"],
                                })
                                st.dataframe(comp_df, use_container_width=True, hide_index=True)

                                # Detailed weights table
                                with st.expander("Ver pesos detallados"):
                                    detail_df = pd.DataFrame({
                                        "Ticker": valid_tickers_rp,
                                        "Risk Parity (%)": [round(w * 100, 2) for w in w_rp],
                                        "Equal Weight (%)": [round(100 / n_assets_rp, 2)] * n_assets_rp,
                                        "Contribución Riesgo (%)": [round(r, 2) for r in rc_pct],
                                    }).sort_values("Risk Parity (%)", ascending=False)
                                    st.dataframe(detail_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error en optimización de cartera: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 10: REBALANCEO DE CARTERA
    # ══════════════════════════════════════════════════════════════
    with tab_rebal:
        try:
            wl_rebal = db.get_watchlist()
            if wl_rebal.empty:
                st.info("Agrega tickers a tu watchlist primero.")
            else:
                tickers_rebal = wl_rebal["ticker"].tolist()
                shares_map = dict(zip(wl_rebal["ticker"], wl_rebal["shares"]))

                st.markdown("<div class='sec-title'>Rebalanceo de Cartera</div>", unsafe_allow_html=True)
                st.markdown("""
                <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                            border-radius:12px;padding:14px;margin-bottom:16px;color:#94a3b8;font-size:12px;'>
                  Define tu asignacion objetivo (%) para cada posicion y calcula las operaciones necesarias
                  para rebalancear tu cartera.
                </div>""", unsafe_allow_html=True)

                # Fetch current prices
                with st.spinner("Obteniendo precios actuales..."):
                    rebal_data = []
                    for tk in tickers_rebal:
                        try:
                            obj = yf.Ticker(tk)
                            price = obj.fast_info.last_price or 0
                            shares = shares_map.get(tk, 0)
                            value = shares * price
                            rebal_data.append({
                                "ticker": tk,
                                "shares": shares,
                                "price": price,
                                "value": value,
                            })
                        except Exception:
                            rebal_data.append({
                                "ticker": tk,
                                "shares": shares_map.get(tk, 0),
                                "price": 0,
                                "value": 0,
                            })

                rebal_df = pd.DataFrame(rebal_data)
                total_value = rebal_df["value"].sum()

                if total_value <= 0:
                    st.warning("El valor total de la cartera es $0. Verifica que tienes acciones con precio valido.")
                else:
                    rebal_df["current_pct"] = (rebal_df["value"] / total_value * 100)

                    # Show current allocation
                    st.markdown(f"**Valor total de cartera: ${total_value:,.2f}**")

                    # Target allocation inputs
                    st.markdown("<div class='sec-title'>Asignacion Objetivo (%)</div>", unsafe_allow_html=True)
                    target_pcts = {}
                    n_cols = min(4, len(tickers_rebal))
                    col_groups = [tickers_rebal[i:i + n_cols] for i in range(0, len(tickers_rebal), n_cols)]

                    for group in col_groups:
                        cols_input = st.columns(len(group))
                        for j, tk in enumerate(group):
                            current = rebal_df.loc[rebal_df["ticker"] == tk, "current_pct"].values[0]
                            target_pcts[tk] = cols_input[j].number_input(
                                f"{tk} (%)",
                                min_value=0.0,
                                max_value=100.0,
                                value=round(current, 1),
                                step=0.5,
                                key=f"rebal_target_{tk}",
                            )

                    total_target = sum(target_pcts.values())
                    if abs(total_target - 100) > 0.1:
                        st.warning(f"La suma de las asignaciones objetivo es {total_target:.1f}%. Debe ser 100%.")
                    else:
                        st.success(f"Total asignacion objetivo: {total_target:.1f}% ✓")

                    # Calculate rebalancing actions
                    if st.button("Calcular Rebalanceo", type="primary", key="rebal_calc_btn"):
                        rebal_rows = []
                        for _, row in rebal_df.iterrows():
                            tk = row["ticker"]
                            current_pct = row["current_pct"]
                            target_pct = target_pcts.get(tk, 0)
                            delta_pct = target_pct - current_pct
                            target_value = total_value * (target_pct / 100)
                            delta_value = target_value - row["value"]
                            shares_to_trade = int(delta_value / row["price"]) if row["price"] > 0 else 0
                            action = "Comprar" if delta_value > 0 else ("Vender" if delta_value < 0 else "Mantener")

                            rebal_rows.append({
                                "Ticker": tk,
                                "Actual %": round(current_pct, 2),
                                "Objetivo %": round(target_pct, 2),
                                "Delta %": round(delta_pct, 2),
                                "Accion": action,
                                "Acciones a Operar": abs(shares_to_trade),
                                "Monto ($)": round(abs(delta_value), 2),
                            })

                        # Add Total row
                        rebal_rows.append({
                            "Ticker": "TOTAL",
                            "Actual %": round(sum(r["Actual %"] for r in rebal_rows), 2),
                            "Objetivo %": round(sum(r["Objetivo %"] for r in rebal_rows), 2),
                            "Delta %": 0,
                            "Accion": "—",
                            "Acciones a Operar": 0,
                            "Monto ($)": 0,
                        })

                        result_df = pd.DataFrame(rebal_rows)

                        def _color_action(val):
                            if val == "Comprar":
                                return "color:#34d399;font-weight:700"
                            elif val == "Vender":
                                return "color:#f87171;font-weight:700"
                            return "color:#475569"

                        def _color_delta(val):
                            if isinstance(val, (int, float)):
                                if val > 0:
                                    return "color:#34d399"
                                elif val < 0:
                                    return "color:#f87171"
                            return "color:#475569"

                        st.markdown("<div class='sec-title'>Plan de Rebalanceo</div>", unsafe_allow_html=True)
                        st.dataframe(
                            result_df.style
                                .map(_color_action, subset=["Accion"])
                                .map(_color_delta, subset=["Delta %"])
                                .format({
                                    "Actual %": "{:.2f}%",
                                    "Objetivo %": "{:.2f}%",
                                    "Delta %": "{:+.2f}%",
                                    "Acciones a Operar": "{:.0f}",
                                    "Monto ($)": "${:,.2f}",
                                }),
                            use_container_width=True,
                            hide_index=True,
                        )

                        # Visual comparison chart
                        chart_data = result_df[result_df["Ticker"] != "TOTAL"]
                        fig_rebal = go.Figure()
                        fig_rebal.add_trace(go.Bar(
                            x=chart_data["Ticker"], y=chart_data["Actual %"],
                            name="Actual", marker_color="#60a5fa",
                            text=[f"{v:.1f}%" for v in chart_data["Actual %"]],
                            textposition="outside", textfont=dict(color="#60a5fa", size=10),
                        ))
                        fig_rebal.add_trace(go.Bar(
                            x=chart_data["Ticker"], y=chart_data["Objetivo %"],
                            name="Objetivo", marker_color="#a78bfa",
                            text=[f"{v:.1f}%" for v in chart_data["Objetivo %"]],
                            textposition="outside", textfont=dict(color="#a78bfa", size=10),
                        ))
                        fig_rebal.update_layout(
                            **DARK, height=350, barmode="group",
                            title=dict(text="Actual vs Objetivo", font=dict(color="#94a3b8", size=13), x=0.5),
                            legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"),
                        )
                        st.plotly_chart(fig_rebal, use_container_width=True)

        except Exception as e:
            st.error(f"Error en rebalanceo: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 11: CHARTS — Comparacion Multi-Metrica
    # ══════════════════════════════════════════════════════════════
    with tab_charts_multi:
        st.markdown("### Comparacion Multi-Metrica")

        # Get watchlist tickers
        _chart_tickers = watchlist_data['ticker'].tolist() if (watchlist_data is not None and not watchlist_data.empty) else []

        if not _chart_tickers:
            st.info("Agrega tickers a tu watchlist para ver charts comparativos")
        else:
            _cc1, _cc2 = st.columns(2)
            with _cc1:
                _metric_type = st.selectbox("Metrica",
                    ["Precio (Normalizado)", "P/E Ratio", "Dividend Yield", "Market Cap", "ROE", "Beta", "Profit Margin"],
                    key="chart_metric_select")
            with _cc2:
                _chart_period = st.selectbox("Periodo",
                    ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
                    index=3,
                    key="chart_period_select")

            if _metric_type == "Precio (Normalizado)":
                # Download historical prices and normalize to base 100
                with st.spinner("Descargando precios..."):
                    _chart_data = yf.download(_chart_tickers[:15], period=_chart_period, progress=False)
                    if not _chart_data.empty:
                        # Handle MultiIndex columns from yfinance
                        if isinstance(_chart_data.columns, pd.MultiIndex):
                            _close = _chart_data['Close']
                            if isinstance(_close, pd.Series):
                                _close = _close.to_frame(name=_chart_tickers[0])
                        else:
                            _close = _chart_data[['Close']] if 'Close' in _chart_data.columns else _chart_data
                            if isinstance(_close, pd.Series):
                                _close = _close.to_frame(name=_chart_tickers[0])
                            elif len(_chart_tickers) == 1:
                                _close.columns = [_chart_tickers[0]]

                        # Drop NaN columns and rows
                        _close = _close.dropna(axis=1, how='all').dropna()

                        if _close.empty:
                            st.warning("No se pudieron obtener datos de precios")
                        else:
                            # Flatten column names if tuples
                            _close.columns = [c[0] if isinstance(c, tuple) else str(c) for c in _close.columns]

                            # Normalize to base 100
                            _normalized = _close / _close.iloc[0] * 100

                            _fig_norm = go.Figure()
                            _colors_list = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                                            '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
                                            '#14b8a6', '#e11d48', '#a855f7', '#22c55e', '#eab308']

                            for _i, _col in enumerate(_normalized.columns):
                                _fig_norm.add_trace(go.Scatter(
                                    x=_normalized.index,
                                    y=_normalized[_col],
                                    name=str(_col),
                                    line=dict(color=_colors_list[_i % len(_colors_list)], width=2)
                                ))

                        _fig_norm.update_layout(**dark_layout(
                            title="Precio Normalizado (Base 100)",
                            yaxis_title="Base 100",
                            height=500,
                            hovermode='x unified'
                        ))
                        st.plotly_chart(_fig_norm, use_container_width=True)
                    else:
                        st.warning("No se pudieron obtener datos de precios")
            else:
                # Fundamental metric comparison - bar chart
                _metric_map = {
                    "P/E Ratio": "trailingPE",
                    "Dividend Yield": "dividendYield",
                    "Market Cap": "marketCap",
                    "ROE": "returnOnEquity",
                    "Beta": "beta",
                    "Profit Margin": "profitMargins",
                }
                _yf_key = _metric_map.get(_metric_type, "trailingPE")

                from cache_utils import get_ticker_info

                _values = {}
                with st.spinner(f"Obteniendo {_metric_type}..."):
                    for _t in _chart_tickers[:15]:
                        try:
                            _info = get_ticker_info(_t)
                            _val = _info.get(_yf_key, None)
                            if _val is not None:
                                # Scale percentages
                                if _yf_key in ['dividendYield', 'returnOnEquity', 'profitMargins']:
                                    _val = _val * 100
                                elif _yf_key == 'marketCap':
                                    _val = _val / 1e9  # To billions
                                _values[_t] = _val
                        except Exception:
                            pass

                if _values:
                    _tickers_sorted = sorted(_values.keys(), key=lambda x: _values[x], reverse=True)
                    _fig_bar = go.Figure()
                    _fig_bar.add_trace(go.Bar(
                        x=_tickers_sorted,
                        y=[_values[_t] for _t in _tickers_sorted],
                        marker_color=['#3b82f6' if _values[_t] >= 0 else '#ef4444' for _t in _tickers_sorted],
                        text=[f"{_values[_t]:.2f}" for _t in _tickers_sorted],
                        textposition='outside'
                    ))

                    _suffix = ""
                    if _yf_key in ['dividendYield', 'returnOnEquity', 'profitMargins']:
                        _suffix = " (%)"
                    elif _yf_key == 'marketCap':
                        _suffix = " ($B)"

                    _fig_bar.update_layout(**dark_layout(
                        title=f"{_metric_type}{_suffix} — Comparacion Watchlist",
                        yaxis_title=f"{_metric_type}{_suffix}",
                        height=450
                    ))
                    st.plotly_chart(_fig_bar, use_container_width=True)
                else:
                    st.warning(f"No se encontraron datos de {_metric_type}")
