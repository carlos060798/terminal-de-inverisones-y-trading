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
import matplotlib.pyplot as plt
from utils import visual_components as vc
from finterm import charts as fc

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

    p_id = st.session_state.get("active_portfolio_id", 1)
    
    # ── Portfolio Lists ──
    list_col1, list_col2, list_col3 = st.columns([3, 2, 1])
    with list_col1:
        available_lists = db.get_watchlist_lists(portfolio_id=p_id)
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
        watchlist_data = db.get_watchlist(portfolio_id=p_id)
    else:
        watchlist_data = db.get_watchlist_by_list(active_list, portfolio_id=p_id)

    # ── TABS ──
    (tab_port, tab_chart, tab_bench, tab_div, tab_calc, tab_corr, tab_earn, tab_sim,
     tab_opt, tab_rebal, tab_charts_multi, tab_stress, tab_volprof, tab_optflow,
     tab_breadth, tab_maxpain, tab_squeeze, tab_seasonal, tab_pairs) = st.tabs([
        "📊 Cartera", "📈 Análisis Técnico", "🏛️ Benchmark", "💰 Dividendos", "🧮 Calculadora",
        "🔗 Correlación", "📅 Earnings", "🎲 Simulación", "📐 Optimización", "⚖️ Rebalanceo", "📊 Charts",
        "🔥 Stress Test", "📊 Vol. Profile", "🕵️ Opciones Flow",
        "📡 Market Breadth", "⚡ Max Pain", "🔀 Short Squeeze", "📅 Estacionalidad", "🔗 Pairs Trading"
    ])

    # ══════════════════════════════════════════════════════════════
    # TAB 1: CARTERA
    # ══════════════════════════════════════════════════════════════
    with tab_port:
        with st.expander("➕  Agregar nueva posición"):
            c1, c2, c3, c4 = st.columns([1, 1, 1, 1.5])
            new_tick  = c1.text_input("Ticker", placeholder="AAPL…")
            new_share = c2.number_input("Acciones", min_value=0.1, step=0.1, value=1.0)
            new_cost  = c3.number_input("Coste ($)", min_value=0.01, step=0.01, value=150.0)
            new_sect  = c4.selectbox("Sector", ["", "Tecnología", "Salud", "Finanzas", "Energía",
                                                 "Consumo", "Industria", "Materiales", "Utilities", "Otro"])
            
            c5, c6, c7 = st.columns([2, 1, 1])
            new_notes = c5.text_input("Notas")
            new_sl = c6.number_input("Stop Loss ($)", min_value=0.0, step=0.01, value=0.0)
            new_tp = c7.number_input("Take Profit ($)", min_value=0.0, step=0.01, value=0.0)
            
            with st.container():
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Agregar ticker", use_container_width=True):
                    if new_tick.strip():
                        target = active_list if active_list != 'Todas' else 'Principal'
                        # Handle 0 as None for SL/TP
                        sl_val = new_sl if new_sl > 0 else None
                        tp_val = new_tp if new_tp > 0 else None
                        db.add_ticker(new_tick.strip(), new_share, new_cost, new_sect, new_notes, target, sl_val, tp_val, portfolio_id=p_id)
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

                    target_list = st.selectbox("Importar a lista:", db.get_watchlist_lists(portfolio_id=p_id), key="import_target_list")

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
                                    db.add_ticker(ticker_val, shares_val, price_val, sector_val, '', target_list, portfolio_id=p_id)
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
                    # Fetch 1 month for sparkline
                    hist = obj.history(period="1mo")
                    price = fi.last_price or 0
                    prev  = hist["Close"].iloc[-2] if len(hist) >= 2 else price
                    chg   = ((price - prev) / prev * 100) if prev else 0
                    info  = obj.info
                    
                    # Sparkline data (Trend)
                    trend_data = hist["Close"].tolist() if not hist.empty else []
                    
                    rows.append({
                        "ticker": tk, 
                        "Precio": price, 
                        "Cambio %": chg,
                        "P/E": info.get("trailingPE"), 
                        "52W High": info.get("fiftyTwoWeekHigh"),
                        "52W Low": info.get("fiftyTwoWeekLow"), 
                        "Mkt Cap": fi.market_cap,
                        "Tendencia": trend_data
                    })
                except Exception:
                    rows.append({
                        "ticker": tk, "Precio": None, "Cambio %": None,
                        "P/E": None, "52W High": None, "52W Low": None, 
                        "Mkt Cap": None, "Tendencia": []
                    })

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
        with k1:
            vc.render_metric_card("Valor Total", fmt(total_val), subtitle=f"{len(df)} posiciones")
        with k2:
            vc.render_metric_card("Capital Invertido", fmt(total_inv), subtitle="Costo base")
        
        with k3:
            vc.render_metric_card("P&L Total", fmt(total_pnl), subtitle=f"{total_pct:+.2f}%", delta=total_pct)
        
        best_pos = df.loc[df["P&L %"].idxmax(), "ticker"] if not df["P&L %"].isna().all() else "—"
        with k4:
            vc.render_metric_card("Mejor Posición", best_pos, subtitle="Máximo retorno")

        st.markdown("""
        <style>
            .watchlist-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 20px;
                padding: 10px 0;
            }
            .ticker-card {
                background: rgba(30, 41, 59, 0.4);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
                padding: 20px;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }
            .ticker-card:hover {
                border-color: rgba(59, 130, 246, 0.5);
                transform: translateY(-5px);
                background: rgba(30, 41, 59, 0.6);
                box-shadow: 0 12px 20px -10px rgba(0, 0, 0, 0.5);
            }
            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 15px;
            }
            .symbol-box {
                display: flex;
                flex-direction: column;
            }
            .card-symbol {
                font-size: 18px;
                font-weight: 800;
                color: #ffffff;
                letter-spacing: -0.5px;
            }
            .card-sector {
                font-size: 10px;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .price-tag {
                font-size: 18px;
                font-weight: 700;
                color: #f8fafc;
                text-align: right;
            }
            .change-tag {
                font-size: 12px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 6px;
                margin-top: 4px;
                display: inline-block;
            }
            .chg-pos { background: rgba(16, 185, 129, 0.1); color: #10b981; }
            .chg-neg { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
            
            .card-metrics {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                margin: 15px 0;
                padding: 12px 0;
                border-top: 1px solid rgba(255,255,255,0.05);
            }
            .m-item {
                display: flex;
                flex-direction: column;
            }
            .m-label { font-size: 9px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
            .m-value { font-size: 12px; font-weight: 600; color: #e2e8f0; }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("<div class='sec-title'>Live Watchlist Grid</div>", unsafe_allow_html=True)
        
        # Grid rendering
        cols_per_row = 3
        for i in range(0, len(df), cols_per_row):
            batch = df.iloc[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for idx, (row_idx, row) in enumerate(batch.iterrows()):
                with cols[idx]:
                    chg_cls = "chg-pos" if row["Cambio %"] >= 0 else "chg-neg"
                    chg_icon = "↑" if row["Cambio %"] >= 0 else "↓"
                    pnl_color = "#10b981" if row["P&L $"] >= 0 else "#ef4444"
                    
                    # Custom Card HTML
                    st.markdown(f"""
                    <div class="ticker-card">
                        <div class="card-header">
                            <div class="symbol-box">
                                <span class="card-symbol">{row['ticker']}</span>
                                <span class="card-sector">{row['sector'] or 'GENERAL'}</span>
                            </div>
                            <div style="text-align:right">
                                <div class="price-tag">${row['Precio']:,.2f}</div>
                                <div class="change-tag {chg_cls}">{chg_icon} {abs(row['Cambio %']):.2f}%</div>
                            </div>
                        </div>
                        
                        <div class="card-metrics">
                            <div class="m-item">
                                <span class="m-label">POSICIÓN</span>
                                <span class="m-value">{row['shares']} shares</span>
                            </div>
                            <div class="m-item">
                                <span class="m-label">VALOR TOTAL</span>
                                <span class="m-value" style="color:#60a5fa">${row['Valor']:,.0f}</span>
                            </div>
                            <div class="m-item">
                                <span class="m-label">P&L TOTAL</span>
                                <span class="m-value" style="color:{pnl_color}">${row['P&L $']:+,.2f}</span>
                            </div>
                            <div class="m-item">
                                <span class="m-label">RETORNO</span>
                                <span class="m-value" style="color:{pnl_color}">{row['P&L %']:+.2f}%</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Sparkline using Plotly for each card
                    if len(row['Tendencia']) > 0:
                        fig_spark = go.Figure()
                        fig_spark.add_trace(go.Scatter(
                            y=row['Tendencia'],
                            mode='lines',
                            fill='tozeroy',
                            line=dict(color=pnl_color, width=2),
                            fillcolor=f"rgba({ '16, 185, 129' if row['P&L $'] >= 0 else '239, 68, 68' }, 0.1)",
                        ))
                        fig_spark.update_layout(
                            **DARK,
                            height=60,
                            margin=dict(l=0, r=0, t=0, b=0),
                            xaxis=dict(visible=False),
                            yaxis=dict(visible=False),
                            showlegend=False,
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})

        # ── EXPORT & AI ──
        st.markdown("<br>", unsafe_allow_html=True)
        exp_col1, exp_col2 = st.columns([1, 1])
        with exp_col1:
            if st.button("🤖 Generar Análisis Estratégico IA", use_container_width=True):
                from services.text_service import analyze_portfolio
                # Convert DF to list of dicts for the service
                pos_dicts = df.to_dict('records')
                with st.spinner("Modelos de IA analizando cartera estratégica..."):
                    res_ai, provider = analyze_portfolio(pos_dicts)
                    if res_ai:
                        st.session_state["portfolio_ai_cache"] = res_ai
                        st.session_state["portfolio_ai_provider"] = provider
        
        if "portfolio_ai_cache" in st.session_state:
             prov_lbl = st.session_state.get("portfolio_ai_provider", "IA")
             st.markdown(f"""
            <div style="background:rgba(16, 185, 129, 0.05); border:1px solid rgba(16, 185, 129, 0.2); padding:20px; border-radius:12px; margin-bottom:20px;">
                <div style="color:#10b981; font-size:12px; font-weight:800; text-transform:uppercase; margin-bottom:10px;">🤖 Quantum Portfolio Intelligence ({prov_lbl})</div>
                <div style="color:#e2e8f0; font-size:13px; line-height:1.6;">{st.session_state["portfolio_ai_cache"]}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # ── EXPORT BUTTONS ────────────────────────────────────────────────────────
        from utils import export_utils
        export_utils.render_export_buttons(df, file_prefix="watchlist_export")
        
        # Calculate Trade Health (0 to 1)
        # 0 = SL, 1 = TP
        def _calc_health(row):
            p = row["Precio"]
            sl = row["stop_loss"]
            tp = row["take_profit"]
            if pd.isna(p) or pd.isna(sl) or pd.isna(tp) or sl >= tp:
                return None
            if p <= sl: return 0.0
            if p >= tp: return 1.0
            return (p - sl) / (tp - sl)

        df["Health"] = df.apply(_calc_health, axis=1)
        
        with st.expander("📝 Ver Tabla Detallada (Legacy View)"):
            tbl = df[["ticker", "sector", "shares", "avg_cost", "Precio", "Cambio %", "Tendencia", "stop_loss", "take_profit", "Health", "Valor", "P&L $", "P&L %"]].copy()
            tbl.columns = ["Ticker", "Sector", "Acciones", "Costo Prom.", "Precio", "Cambio %", "Tendencia (30d)", "SL", "TP", "Trade Health", "Valor ($)", "P&L ($)", "P&L %"]

            def clr(v):
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return "color:#475569"
                return "color:#34d399" if v >= 0 else "color:#f87171"

            st.dataframe(
                tbl.style.map(clr, subset=["Cambio %", "P&L ($)", "P&L %"])
                         .format({"Costo Prom.": "${:.2f}", "Precio": "${:.2f}", "Cambio %": "{:+.2f}%",
                                  "SL": "${:.2f}", "TP": "${:.2f}",
                                  "Valor ($)": "${:,.0f}", "P&L ($)": "${:+,.0f}", "P&L %": "{:+.2f}%", "Acciones": "{:.2f}"},
                                  na_rep="—"),
                use_container_width=True, hide_index=True,
                column_config={
                    "Tendencia (30d)": st.column_config.AreaChartColumn(
                        "Tendencia (30d)",
                        help="Evolución del precio último mes",
                        width="medium"
                    ),
                    "Trade Health": st.column_config.ProgressColumn(
                        "Estado Trade (SL→TP)",
                        help="Posición del precio respecto al SL (0%) y TP (100%)",
                        format="%.2f",
                        min_value=0,
                        max_value=1,
                        width="medium"
                    )
                }
            )

        # ── Charts ──
        st.markdown("<div class='sec-title'>Distribución & Performance</div>", unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            pie_d = df[df["Valor"] > 0]
            if not pie_d.empty:
                # Usamos el componente estandarizado de distribución de activos
                weights = dict(zip(pie_d["ticker"], pie_d["Valor"]))
                fig_p = fc.create_allocation_donut(weights)
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
                                portfolio_id=p_id
                            )
                            st.success(f"Notas guardadas para {note_ticker}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar notas: {e}")
        except Exception as e:
            st.info(f"No se pudo cargar el editor de notas: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 2: ANÁLISIS TÉCNICO (TradingView)
    # ══════════════════════════════════════════════════════════════
    with tab_chart:
        import streamlit.components.v1 as components
        wl2 = db.get_watchlist(portfolio_id=p_id)
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

                # ── Combined Chart: TradingView Advanced Chart ──
                html_tv = f"""
                <div class="tradingview-widget-container" style="height:650px;width:100%;">
                  <div id="tradingview_adv_{sel}" style="height:100%;width:100%;"></div>
                  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                  <script type="text/javascript">
                  new TradingView.widget({{
                    "autosize": true,
                    "symbol": "{sel}",
                    "interval": "D",
                    "timezone": "America/New_York",
                    "theme": "dark",
                    "style": "1",
                    "locale": "es",
                    "toolbar_bg": "#0a0a0a",
                    "enable_publishing": false,
                    "hide_side_toolbar": false,
                    "allow_symbol_change": false,
                    "details": true,
                    "studies": ["STD;MACD", "STD;RSI"],
                    "container_id": "tradingview_adv_{sel}",
                    "backgroundColor": "rgba(10,10,10,1)",
                    "gridColor": "rgba(40,40,40,0.3)"
                  }});
                  </script>
                </div>
                """
                components.html(html_tv, height=660)

        # ── ADVANCED INDICATORS (pandas-ta) ──
        if HAS_PANDAS_TA:
            with st.expander("📊 Indicadores Técnicos Avanzados"):
                adv_ticker = st.selectbox("Ticker para análisis avanzado", tickers2, key="adv_ta_ticker")
                adv_period = st.selectbox("Período", ["6mo", "1y", "2y"], index=1, key="adv_ta_period")

                adv_indicators = st.multiselect(
                    "Seleccionar indicadores",
                    ["Ichimoku Cloud", "ADX", "Stochastic", "ATR", "OBV", "Volume Profile (VPVR)", "Volume Delta"],
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

                                elif indicator == "Volume Profile (VPVR)":
                                    close_col = adv_data["Close"]
                                    vol_col = adv_data["Volume"]
                                    if not close_col.empty and not vol_col.empty:
                                        min_p, max_p = close_col.min(), close_col.max()
                                        bins = pd.cut(close_col, bins=50)
                                        vp = vol_col.groupby(bins).sum()
                                        vp.index = vp.index.map(lambda x: x.mid)
                                        fig_vp = go.Figure()
                                        fig_vp.add_trace(go.Bar(
                                            x=vp.values, y=vp.index, orientation='h',
                                            marker=dict(color='rgba(96, 165, 250, 0.4)', line=dict(color='rgba(96, 165, 250, 0.8)', width=1)),
                                            name="VPVR"
                                        ))
                                        fig_vp.update_layout(**DARK, height=400,
                                            title=dict(text=f"Volume Profile (VPVR) — {adv_ticker}", font=dict(color="#94a3b8", size=13), x=0.5), showlegend=False)
                                        st.plotly_chart(fig_vp, use_container_width=True)

                                elif indicator == "Volume Delta":
                                    c_col, o_col, v_col = adv_data["Close"], adv_data["Open"], adv_data["Volume"]
                                    if not c_col.empty and not o_col.empty and not v_col.empty:
                                        deltas = []
                                        colors = []
                                        for i in range(len(c_col)):
                                            if c_col.iloc[i] > o_col.iloc[i]:
                                                deltas.append(v_col.iloc[i])
                                                colors.append('#10b981')
                                            else:
                                                deltas.append(-v_col.iloc[i])
                                                colors.append('#ef4444')
                                        fig_vd = go.Figure()
                                        fig_vd.add_trace(go.Bar(x=adv_data.index, y=deltas, marker_color=colors, name="Delta"))
                                        fig_vd.update_layout(**DARK, height=300,
                                            title=dict(text=f"Volume Delta — {adv_ticker}", font=dict(color="#94a3b8", size=13), x=0.5), showlegend=False)
                                        st.plotly_chart(fig_vd, use_container_width=True)

                    except Exception as e:
                        st.error(f"Error calculando indicadores: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 3: BENCHMARK vs S&P500
    # ══════════════════════════════════════════════════════════════
    with tab_bench:
        wl3 = db.get_watchlist(portfolio_id=p_id)
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
        wl4 = db.get_watchlist(portfolio_id=p_id)
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
        st.markdown("<div class='sec-title'>🧮 Calculadora de Tamaño (Kelly Criterion)</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                    border-radius:12px;padding:16px;margin-bottom:20px;color:#94a3b8;font-size:13px;'>
          <b>Criterio de Kelly:</b> Determina matemáticamente el tamaño óptimo de la apuesta basándose en la ventaja estadística.<br>
          <b>Regla de Kelly Fraccionario:</b> Se recomienda usar medio Kelly (0.5) para mayor estabilidad.
        </div>""", unsafe_allow_html=True)

        pc1, pc2 = st.columns([1, 1.2])
        with pc1:
            st.markdown("##### ⚙️ Parámetros de Estrategia")
            capital = st.number_input("Capital total ($)", min_value=0.0, value=10000.0, step=1000.0)
            win_rate = st.slider("Tasa de Acierto (Win Rate %)", 10, 90, 55) / 100
            profit_loss_ratio = st.number_input("Ratio Profit/Loss (Promedio)", min_value=0.1, value=2.0, step=0.1)
            kelly_fraction = st.select_slider("Fracción de Kelly", options=[0.25, 0.5, 1.0], value=0.5, help="1.0 = Kelly Full, 0.5 = Medio Kelly (Recomendado)")
            
            st.markdown("---")
            st.markdown("##### 🎯 Parámetros del Trade")
            entry_p = st.number_input("Precio entrada ($)", min_value=0.01, value=150.0)
            stop_p = st.number_input("Precio Stop Loss ($)", min_value=0.01, value=140.0)

        with pc2:
            # Kelly Formula: K% = W - [(1 - W) / R]
            # W = win rate, R = profit/loss ratio
            kelly_pct = win_rate - ((1 - win_rate) / profit_loss_ratio)
            suggested_kelly = max(0, kelly_pct * kelly_fraction)
            
            risk_amount = capital * suggested_kelly
            risk_per_share = abs(entry_p - stop_p)
            shares_to_buy = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
            position_value = shares_to_buy * entry_p
            
            # UI display
            st.markdown(f"""
            <div style='background:linear-gradient(135deg,#0d1f35,#0a1628);border:1px solid #1e3a5f;
                        border-radius:14px;padding:24px;'>
              <div style='color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:15px;'>Asignación Optimizada</div>
              
              <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;'>
                 <span style='color:#e2e8f0;font-size:14px;'>Kelly Sugerido ({kelly_fraction}x):</span>
                 <span style='color:#60a5fa;font-size:24px;font-weight:800;'>{suggested_kelly*100:.1f}%</span>
              </div>
              
              <div style='display:grid;grid-template-columns:1fr 1fr;gap:15px;'>
                <div style='background:rgba(255,255,255,0.03);padding:15px;border-radius:10px;'>
                   <div style='color:#94a3b8;font-size:10px;'>ACCIONES</div>
                   <div style='color:#facc15;font-size:20px;font-weight:700;'>{shares_to_buy}</div>
                </div>
                <div style='background:rgba(255,255,255,0.03);padding:15px;border-radius:10px;'>
                   <div style='color:#94a3b8;font-size:10px;'>VALOR POSICIÓN</div>
                   <div style='color:#34d399;font-size:20px;font-weight:700;'>${position_value:,.0f}</div>
                </div>
              </div>
              
              <div style='margin-top:20px;padding:15px;background:rgba(248,113,113,0.1);border:1px solid rgba(248,113,113,0.2);border-radius:10px;'>
                <div style='color:#f87171;font-size:11px;'>RIESGO MÁXIMO EN $</div>
                <div style='color:#f87171;font-size:18px;font-weight:700;'>${risk_amount:,.2f}</div>
              </div>
              
              <div style='margin-top:15px;font-size:11px;color:#64748b;line-height:1.4;'>
                ⚠️ <i>Nota: Si el Kelly es negativo, tu estrategia actual no tiene ventaja estadística (Edge) y no deberías operar.</i>
              </div>
            </div>""", unsafe_allow_html=True)
            
            # Interactive Chart for Kelly Curve
            curve_data = []
            for r in np.arange(0.5, 5.5, 0.5):
                k = win_rate - ((1 - win_rate) / r)
                curve_data.append({"Ratio R:R": r, "Kelly %": max(0, k * 100)})
            
            c_df = pd.DataFrame(curve_data)
            fig_k = px.line(c_df, x="Ratio R:R", y="Kelly %", title="Curva de Sensibilidad Kelly vs R:R")
            fig_k.add_vline(x=profit_loss_ratio, line_dash="dash", line_color="#fac415")
            fig_k.update_layout(height=250, **dark_layout(margin=dict(t=30, b=0, l=0, r=0)))
            st.plotly_chart(fig_k, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 6: CORRELACIÓN
    # ══════════════════════════════════════════════════════════════
    with tab_corr:
        try:
            wl_corr = db.get_watchlist(portfolio_id=p_id)
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
                        fig_corr = fc.create_correlation_heatmap(corr)
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
            wl_earn = db.get_watchlist(portfolio_id=p_id)
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
            wl_sim = db.get_watchlist(portfolio_id=p_id)
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
            rows = db.get_watchlist(portfolio_id=p_id)
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

                                # Usamos el componente institucional de finterm
                                # Usamos el componente institucional de finterm
                                # results[:, 0] = Vol, results[:, 1] = Ret
                                fig_ef = fc.create_efficient_frontier_chart(
                                    results,
                                    max_sharpe=[perf_sharpe[1], perf_sharpe[0]],
                                    min_vol=[perf_minvol[1], perf_minvol[0]]
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

                                # ── PHASE 2: SCIPY EFFICIENT FRONTIER ──
                                if HAS_SCIPY:
                                    st.markdown("---")
                                    st.markdown("<div class='sec-title'>📐 Optimización: Retorno Máximo vs Riesgo</div>", unsafe_allow_html=True)
                                    st.caption("Frontera Eficiente calculada matemáticamente con Scipy (Finterm Light Optimizer).")
                                    
                                    try:
                                        # Maximize Sharpe Ratio
                                        def neg_sharpe(weights, mean_returns, cov_matrix, risk_free_rate):
                                            p_ret = np.sum(mean_returns * weights) * 252
                                            p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix * 252, weights)))
                                            return -(p_ret - risk_free_rate) / p_vol
                                        
                                        args = (mu_rp / 252, cov_matrix / 252, 0.0)
                                        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
                                        bounds = tuple((0.0, 1.0) for asset in range(n_assets_rp))
                                        
                                        result_sharpe = scipy_minimize(neg_sharpe, n_assets_rp * [1. / n_assets_rp,], args=args,
                                                method='SLSQP', bounds=bounds, constraints=constraints)
                                        
                                        w_sharpe = result_sharpe.x
                                        max_ret = np.sum((mu_rp/252) * w_sharpe) * 252 * 100
                                        max_vol = np.sqrt(np.dot(w_sharpe.T, np.dot((cov_matrix/252) * 252, w_sharpe))) * 100
                                        max_sharpe = max_ret / max_vol if max_vol > 0 else 0
                                        
                                        hr_c1, hr_c2 = st.columns([1, 1])
                                        with hr_c1:
                                            df_sharpe = pd.DataFrame({'Ticker': valid_tickers_rp, 'Peso': w_sharpe * 100})
                                            df_sharpe = df_sharpe[df_sharpe['Peso'] > 1.0] # Only show >1%
                                            
                                            fig_h = px.pie(df_sharpe, values='Peso', names='Ticker', 
                                                          title="Distribución Optima (Max Sharpe)",
                                                          hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                                            fig_h.update_layout(**DARK, height=400)
                                            st.plotly_chart(fig_h, use_container_width=True)
                                        
                                        with hr_c2:
                                            st.markdown("<br><br>", unsafe_allow_html=True)
                                            st.markdown(f"""
                                            <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:12px;padding:20px;'>
                                              <div style='color:#94a3b8;font-size:12px;margin-bottom:10px;'>METRICAS MAX SHARPE</div>
                                              <div style='font-size:20px;font-weight:700;color:#60a5fa;'>Retorno Esperado: {max_ret:.2f}%</div>
                                              <div style='font-size:20px;font-weight:700;color:#f87171;'>Volatilidad: {max_vol:.2f}%</div>
                                              <div style='font-size:20px;font-weight:700;color:#34d399;'>Sharpe Ratio: {max_sharpe:.2f}</div>
                                            </div>""", unsafe_allow_html=True)
                                            
                                            if st.button("Aplicar Pesos Máx Sharpe", key="apply_sharpe"):
                                                for tk, weight in zip(df_sharpe['Ticker'], df_sharpe['Peso']):
                                                    st.session_state[f"rebal_target_{tk}"] = round(weight, 2)
                                                st.success("Pesos cargados en Rebalanceo.")
                                                
                                    except Exception as e_h:
                                        st.error(f"Error en Scipy: {e_h}")
                                else:
                                    st.info("Requiere Scipy.")
        except Exception as e:
            st.error(f"Error en optimización de cartera: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 10: REBALANCEO DE CARTERA
    # ══════════════════════════════════════════════════════════════
    with tab_rebal:
        try:
            wl_rebal = db.get_watchlist(portfolio_id=p_id)
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

    # ══════════════════════════════════════════════════════════════
    # TAB 12: STRESS TEST (MONTE CARLO)
    # ══════════════════════════════════════════════════════════════
    with tab_stress:
        wl_stress = db.get_watchlist(portfolio_id=p_id)
        if wl_stress.empty:
            st.info("Agrega tickers a tu watchlist primero.")
        else:
            st.markdown("<div class='sec-title'>🔥 Monte Carlo Stress Test</div>", unsafe_allow_html=True)
            st.caption("Simulación de 1,000 caminos aleatorios correlacionados para proyectar el rango de valores del portafolio a 1 año.")

            sc1, sc2, sc3 = st.columns(3)
            n_sims = sc1.number_input("Simulaciones", value=1000, min_value=100, max_value=5000, step=100)
            n_days = sc2.number_input("Días a proyectar", value=252, min_value=30, max_value=504, step=21)
            hist_per = sc3.selectbox("Historial base", ["1y", "2y", "3y", "5y"], index=1)

            if st.button("🚀 Ejecutar Simulación", type="primary", use_container_width=True, key="mc_run"):
                with st.spinner("Ejecutando simulación Monte Carlo..."):
                    from utils.monte_carlo import run_monte_carlo

                    tickers_mc = wl_stress["ticker"].tolist()
                    shares = wl_stress["shares"].tolist()
                    costs = wl_stress["avg_cost"].tolist()

                    # Get live prices for weights
                    try:
                        # Using yfinance to download prices directly
                        prices_df = yf.download(tickers_mc, period="1d", progress=False)["Close"]
                        if isinstance(prices_df, pd.Series):
                            prices_mc = {tickers_mc[0]: prices_df.iloc[-1]}
                        else:
                            prices_mc = {t: prices_df[t].iloc[-1] for t in tickers_mc if t in prices_df.columns}
                            
                        values = [shares[i] * prices_mc.get(tickers_mc[i], costs[i]) for i in range(len(tickers_mc))]
                    except Exception as e:
                        print(f"Fallback due to price error: {e}")
                        values = [shares[i] * costs[i] for i in range(len(tickers_mc))]

                    total_val_mc = sum(values)
                    weights_mc = [v / total_val_mc for v in values] if total_val_mc > 0 else [1/len(tickers_mc)] * len(tickers_mc)

                    result = run_monte_carlo(
                        tickers_mc, weights_mc, total_val_mc,
                        n_simulations=n_sims, n_days=n_days, history_period=hist_per
                    )

                if "error" in result:
                    st.error(result["error"])
                else:
                    stats = result["stats"]

                    # KPIs
                    mk1, mk2, mk3, mk4 = st.columns(4)
                    mk1.markdown(kpi("Valor Inicial", fmt(stats["initial_value"]), f"{stats['n_assets']} activos", "blue"), unsafe_allow_html=True)
                    mk2.markdown(kpi("Valor Medio Final", fmt(stats["mean_final"]), f"{n_days} días", "green" if stats["mean_final"] > stats["initial_value"] else "red"), unsafe_allow_html=True)
                    mk3.markdown(kpi("VaR 95%", f"${result['var_95']:+,.0f}", "pérdida máxima probable", "red"), unsafe_allow_html=True)
                    mk4.markdown(kpi("Prob. de Pérdida", f"{stats['prob_loss_pct']:.1f}%", "en el horizonte", "red" if stats["prob_loss_pct"] > 50 else "green"), unsafe_allow_html=True)

                    # Cone Chart
                    days_range = list(range(n_days + 1))

                    fig_mc = go.Figure()
                    # 5-95 percentile band
                    fig_mc.add_trace(go.Scatter(x=days_range, y=result["p95"], mode="lines", line=dict(width=0), showlegend=False))
                    fig_mc.add_trace(go.Scatter(x=days_range, y=result["p5"], mode="lines", fill="tonexty", fillcolor="rgba(239,68,68,0.12)", line=dict(width=0), name="Rango 90%"))
                    # 25-75 percentile band
                    fig_mc.add_trace(go.Scatter(x=days_range, y=result["p75"], mode="lines", line=dict(width=0), showlegend=False))
                    fig_mc.add_trace(go.Scatter(x=days_range, y=result["p25"], mode="lines", fill="tonexty", fillcolor="rgba(96,165,250,0.2)", line=dict(width=0), name="Rango 50%"))
                    # Mean path
                    fig_mc.add_trace(go.Scatter(x=days_range, y=result["mean_path"], mode="lines", line=dict(color="#34d399", width=2.5), name="Media"))
                    # Initial value line
                    fig_mc.add_hline(y=total_val_mc, line_dash="dot", line_color="#fbbf24", annotation_text=f"Valor Actual: {fmt(total_val_mc)}")

                    fig_mc.update_layout(
                        **DARK, height=500,
                        title=dict(text=f"Proyección Monte Carlo ({n_sims} simulaciones, {n_days} días)", font=dict(color="#94a3b8", size=14), x=0.5),
                        xaxis_title="Días", yaxis_title="Valor del Portafolio ($)",
                        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"))
                    )
                    st.plotly_chart(fig_mc, use_container_width=True)

                    # Distribution histogram
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(
                        x=result["final_values"], nbinsx=60,
                        marker_color="rgba(96,165,250,0.6)", marker_line=dict(color="#60a5fa", width=0.5)
                    ))
                    fig_dist.add_vline(x=total_val_mc, line_dash="dash", line_color="#fbbf24", annotation_text="Valor Actual")
                    fig_dist.add_vline(x=total_val_mc + result["var_95"], line_dash="dash", line_color="#f87171", annotation_text=f"VaR 95%: {fmt(total_val_mc + result['var_95'])}")
                    fig_dist.update_layout(**DARK, height=350, title=dict(text="Distribución de Valores Finales", font=dict(color="#94a3b8", size=13), x=0.5),
                                           xaxis_title="Valor Final ($)", yaxis_title="Frecuencia")
                    st.plotly_chart(fig_dist, use_container_width=True)

                    st.markdown(f"""
                    <div style='background:rgba(239,68,68,0.1);border:1px solid #f87171;padding:15px;border-radius:10px;'>
                        <b style='color:#f87171;'>⚠️ Resumen de Riesgo</b><br>
                        <span style='color:#94a3b8;'>VaR 95%:</span> <b>${result['var_95']:+,.0f}</b> |
                        <span style='color:#94a3b8;'>CVaR 95%:</span> <b>${result['cvar_95']:+,.0f}</b> |
                        <span style='color:#94a3b8;'>Peor caso:</span> <b>{fmt(stats['worst_case'])}</b> |
                        <span style='color:#94a3b8;'>Mejor caso:</span> <b>{fmt(stats['best_case'])}</b>
                    </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 13: VOLUME PROFILE
    # ══════════════════════════════════════════════════════════════
    with tab_volprof:
        wl_vp = db.get_watchlist(portfolio_id=p_id)
        if wl_vp.empty:
            st.info("Agrega tickers a tu watchlist primero.")
        else:
            st.markdown("<div class='sec-title'>📊 Perfil de Volumen</div>", unsafe_allow_html=True)
            st.caption("Distribución de volumen por niveles de precio. Identifica POC, zonas de alta liquidez (HVN) y vacíos (LVN).")

            vc1, vc2, vc3, vc4 = st.columns(4)
            vp_ticker = vc1.selectbox("Ticker", wl_vp["ticker"].tolist(), key="vp_tick")
            vp_interval = vc2.selectbox("Intervalo", ["1h", "4h", "1d"], index=1, key="vp_int")
            vp_period = vc3.selectbox("Período", ["5d", "1mo", "3mo", "6mo"], index=1, key="vp_per")
            vp_bins = vc4.number_input("Niveles", value=50, min_value=20, max_value=100, step=5, key="vp_bins")

            if st.button("Calcular Perfil de Volumen", type="primary", use_container_width=True, key="vp_run"):
                with st.spinner("Calculando perfil de volumen..."):
                    from utils.volume_profile import compute_volume_profile
                    vp_result = compute_volume_profile(vp_ticker, interval=vp_interval, period=vp_period, n_bins=vp_bins)

                if "error" in vp_result:
                    st.error(vp_result["error"])
                else:
                    profile = vp_result["profile"]
                    poc = vp_result["poc_price"]
                    va_high = vp_result["value_area_high"]
                    va_low = vp_result["value_area_low"]

                    vk1, vk2, vk3 = st.columns(3)
                    vk1.markdown(kpi("POC (Point of Control)", f"${poc:,.2f}", "máximo volumen", "blue"), unsafe_allow_html=True)
                    vk2.markdown(kpi("Value Area High", f"${va_high:,.2f}", "70% vol superior", "green"), unsafe_allow_html=True)
                    vk3.markdown(kpi("Value Area Low", f"${va_low:,.2f}", "70% vol inferior", "red"), unsafe_allow_html=True)

                    # Horizontal bar chart
                    colors = []
                    for _, row in profile.iterrows():
                        if row["node_type"] == "POC":
                            colors.append("#fbbf24")
                        elif row["node_type"] == "HVN":
                            colors.append("#60a5fa")
                        elif row["node_type"] == "LVN":
                            colors.append("rgba(96,165,250,0.2)")
                        else:
                            colors.append("rgba(96,165,250,0.5)")

                    fig_vp = go.Figure()
                    fig_vp.add_trace(go.Bar(
                        y=profile["price_level"], x=profile["volume"],
                        orientation="h", marker_color=colors,
                        hovertemplate="Precio: $%{y:.2f}<br>Volumen: %{x:,.0f}<extra></extra>"
                    ))

                    # POC line
                    fig_vp.add_hline(y=poc, line_dash="solid", line_color="#fbbf24", line_width=2,
                                    annotation_text=f"POC: ${poc:.2f}", annotation_font_color="#fbbf24")
                    # Value Area
                    fig_vp.add_hrect(y0=va_low, y1=va_high, fillcolor="rgba(96,165,250,0.08)", line_width=0,
                                    annotation_text="Value Area (70%)", annotation_font_color="#60a5fa")

                    fig_vp.update_layout(
                        **DARK, height=600,
                        title=dict(text=f"Volume Profile — {vp_ticker} ({vp_interval} / {vp_period})", font=dict(color="#94a3b8", size=14), x=0.5),
                        xaxis_title="Volumen", yaxis_title="Precio ($)",
                        showlegend=False
                    )
                    st.plotly_chart(fig_vp, use_container_width=True)

                    # Leyenda
                    st.markdown("""
                    <div style='display:flex;gap:20px;justify-content:center;'>
                        <span>🟡 <b>POC</b> (Precio de Control)</span>
                        <span>🔵 <b>HVN</b> (Alta Liquidez)</span>
                        <span>⚪ <b>LVN</b> (Vacío de Volumen)</span>
                    </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 14: OPTIONS FLOW
    # ══════════════════════════════════════════════════════════════
    with tab_optflow:
        wl_opt = db.get_watchlist(portfolio_id=p_id)
        if wl_opt.empty:
            st.info("Agrega tickers a tu watchlist primero.")
        else:
            st.markdown("<div class='sec-title'>🕵️ Escáner de Opciones Inusuales</div>", unsafe_allow_html=True)
            st.caption("Detecta actividad inusual en cadenas de opciones (Volume >> Open Interest) que puede indicar posicionamiento institucional.")

            oc1, oc2 = st.columns(2)
            opt_n = oc1.number_input("Top N Tickers a escanear", value=5, min_value=1, max_value=10, step=1)
            opt_threshold = oc2.number_input("Umbral Vol/OI", value=2.0, min_value=1.0, max_value=10.0, step=0.5)

            if st.button("🔍 Escanear Opciones", type="primary", use_container_width=True, key="opt_scan"):
                with st.spinner(f"Escaneando cadenas de opciones para los top {opt_n} tickers..."):
                    from utils.options_scanner import scan_unusual_options, get_options_sentiment
                    opt_tickers = wl_opt["ticker"].tolist()
                    opt_df = scan_unusual_options(opt_tickers, max_tickers=opt_n, vol_oi_threshold=opt_threshold)
                    sentiment = get_options_sentiment(opt_df)

                if opt_df.empty:
                    st.info("No se encontraron anomalías con los filtros actuales. Intenta reducir el umbral Vol/OI.")
                else:
                    # Sentiment KPIs
                    ok1, ok2, ok3, ok4 = st.columns(4)
                    ok1.markdown(kpi("Señal", sentiment["signal"], "", "blue"), unsafe_allow_html=True)
                    ok2.markdown(kpi("Calls Inusuales", str(sentiment["call_count"]), f"Vol: {sentiment.get('call_volume', 0):,}", "green"), unsafe_allow_html=True)
                    ok3.markdown(kpi("Puts Inusuales", str(sentiment["put_count"]), f"Vol: {sentiment.get('put_volume', 0):,}", "red"), unsafe_allow_html=True)
                    ok4.markdown(kpi("Ratio Call/Put", f"{sentiment['ratio']:.2f}", "Vol. ponderado", "blue"), unsafe_allow_html=True)

                    st.markdown("<div class='sec-title'>Anomalías Detectadas (ordenadas por urgencia)</div>", unsafe_allow_html=True)

                    def _opt_color(val):
                        if isinstance(val, str) and "CALL" in val:
                            return "color:#34d399"
                        if isinstance(val, str) and "PUT" in val:
                            return "color:#f87171"
                        return ""

                    from utils import export_utils
                    export_utils.render_export_buttons(opt_df, file_prefix="options_flow_unusals")

                    st.dataframe(
                        opt_df.style.map(_opt_color, subset=["Tipo"]).format({
                            "Strike": "${:.2f}", "Last Price": "${:.2f}",
                            "Volume": "{:,}", "Open Interest": "{:,}",
                            "IV": "{:.1f}%", "Vol/OI": "{:.1f}x",
                            "Bid": "${:.2f}", "Ask": "${:.2f}"
                        }),
                        use_container_width=True, hide_index=True, height=400
                    )

    # ══════════════════════════════════════════════════════════════
    # TAB 15: MARKET BREADTH
    # ══════════════════════════════════════════════════════════════
    with tab_breadth:
        st.markdown("<div class='sec-title'>📡 Market Breadth Dashboard</div>", unsafe_allow_html=True)
        st.caption("Salud real del mercado: % de acciones del S&P 500 por encima de su SMA-50 y SMA-200. Una divergencia (índice sube, breadth cae) es señal de techo institucional.")

        sample_n = st.slider("Muestra de tickers a analizar", 50, 300, 100, step=50, key="breadth_n")
        if st.button("📡 Calcular Market Breadth", type="primary", use_container_width=True, key="breadth_run"):
            with st.spinner("Descargando datos del mercado..."):
                from utils.market_breadth import compute_market_breadth
                breadth = compute_market_breadth(sample_size=sample_n)

            if "error" in breadth:
                st.error(breadth["error"])
            else:
                bk1, bk2, bk3, bk4 = st.columns(4)
                col50  = "#34d399" if breadth["pct_above_50"] >= 60 else ("#fbbf24" if breadth["pct_above_50"] >= 40 else "#f87171")
                col200 = "#34d399" if breadth["pct_above_200"] >= 60 else ("#fbbf24" if breadth["pct_above_200"] >= 40 else "#f87171")
                bk1.markdown(kpi("% sobre SMA-50",  f"{breadth['pct_above_50']}%",  breadth["signal_50"],  "blue"), unsafe_allow_html=True)
                bk2.markdown(kpi("% sobre SMA-200", f"{breadth['pct_above_200']}%", breadth["signal_200"], "blue"), unsafe_allow_html=True)
                bk3.markdown(kpi("Tickers analizados", str(breadth["total_analyzed"]), "muestra S&P 500", "blue"), unsafe_allow_html=True)
                bk4.markdown(kpi("Sobre SMA-200", f"{breadth['above_200']}/{breadth['total_analyzed']}", "activos", "green"), unsafe_allow_html=True)

                # Gauge chart (SMA-50)
                fig_b50 = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=breadth["pct_above_50"],
                    number={"suffix": "%", "font": {"color": col50, "size": 40}},
                    title={"text": "% Acciones sobre SMA-50", "font": {"color": "#94a3b8", "size": 13}},
                    gauge={
                        "axis": {"range": [0, 100], "dtick": 25},
                        "bar": {"color": col50},
                        "bgcolor": "#0a0a0a",
                        "steps": [
                            {"range": [0, 30],  "color": "rgba(239,68,68,0.15)"},
                            {"range": [30, 50], "color": "rgba(251,191,36,0.1)"},
                            {"range": [50, 70], "color": "rgba(148,163,184,0.08)"},
                            {"range": [70, 100],"color": "rgba(52,211,153,0.15)"},
                        ],
                    }
                ))
                fig_b50.update_layout(**DARK, height=280)

                fig_b200 = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=breadth["pct_above_200"],
                    number={"suffix": "%", "font": {"color": col200, "size": 40}},
                    title={"text": "% Acciones sobre SMA-200", "font": {"color": "#94a3b8", "size": 13}},
                    gauge={
                        "axis": {"range": [0, 100], "dtick": 25},
                        "bar": {"color": col200},
                        "bgcolor": "#0a0a0a",
                        "steps": [
                            {"range": [0, 30],  "color": "rgba(239,68,68,0.15)"},
                            {"range": [30, 50], "color": "rgba(251,191,36,0.1)"},
                            {"range": [50, 70], "color": "rgba(148,163,184,0.08)"},
                            {"range": [70, 100],"color": "rgba(52,211,153,0.15)"},
                        ],
                    }
                ))
                fig_b200.update_layout(**DARK, height=280)

                gc1, gc2 = st.columns(2)
                gc1.plotly_chart(fig_b50,  use_container_width=True)
                gc2.plotly_chart(fig_b200, use_container_width=True)

                # Historical breadth lines
                if breadth.get("hist_50") is not None and len(breadth["hist_50"]) > 0:
                    fig_hist = go.Figure()
                    hist50  = breadth["hist_50"].dropna()
                    hist200 = breadth["hist_200"].dropna() if breadth.get("hist_200") is not None else None
                    fig_hist.add_trace(go.Scatter(x=hist50.index, y=hist50.values, mode="lines",
                                                  line=dict(color="#60a5fa", width=2), name="% sobre SMA-50"))
                    if hist200 is not None and len(hist200) > 0:
                        fig_hist.add_trace(go.Scatter(x=hist200.index, y=hist200.values, mode="lines",
                                                      line=dict(color="#34d399", width=2), name="% sobre SMA-200"))
                    fig_hist.add_hline(y=50, line_dash="dot", line_color="#fbbf24", annotation_text="50%")
                    fig_hist.update_layout(**DARK, height=300,
                                           title=dict(text="Breadth Histórico (Semanal)", font=dict(color="#94a3b8", size=13), x=0.5),
                                           xaxis_title="Fecha")
                    fig_hist.update_yaxes(title_text="%", range=[0, 100])
                    st.plotly_chart(fig_hist, use_container_width=True)

                # Sector heatmap
                if breadth.get("sectors"):
                    sec_data = breadth["sectors"]
                    sec_df = pd.DataFrame([
                        {"Sector": name,
                         "ETF": d["etf"],
                         "Precio": f"${d['price']:.2f}",
                         "Sobre SMA-50": "✅" if d["above_50"] else "❌",
                         "Sobre SMA-200": "✅" if d["above_200"] else "❌"}
                        for name, d in sec_data.items()
                    ])
                    st.markdown("<div class='sec-title' style='font-size:13px;'>Desglose por Sector (ETFs)</div>", unsafe_allow_html=True)
                    st.dataframe(sec_df, use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 16: MAX PAIN
    # ══════════════════════════════════════════════════════════════
    with tab_maxpain:
        wl_mp = db.get_watchlist(portfolio_id=p_id)
        st.markdown("<div class='sec-title'>⚡ Calculadora de Max Pain</div>", unsafe_allow_html=True)
        st.caption("El nivel de precio donde el mayor número de opciones expira sin valor. Los Market Makers suelen anclar el precio aquí durante las semanas de vencimiento.")

        mp1, mp2 = st.columns(2)
        mp_ticker = mp1.text_input("Ticker", value=wl_mp["ticker"].iloc[0] if not wl_mp.empty else "SPY", key="mp_ticker")
        from utils.max_pain import get_expirations
        expirations = get_expirations(mp_ticker) if mp_ticker else []
        mp_exp = mp2.selectbox("Expiración", expirations if expirations else ["Sin datos"], key="mp_exp")

        if st.button("⚡ Calcular Max Pain", type="primary", use_container_width=True, key="mp_run"):
            if not expirations:
                st.error("No hay fechas de expiración disponibles para este ticker.")
            else:
                with st.spinner("Calculando Max Pain..."):
                    from utils.max_pain import get_max_pain
                    mp_result = get_max_pain(mp_ticker, mp_exp)

                if "error" in mp_result:
                    st.error(mp_result["error"])
                else:
                    mpk1, mpk2, mpk3 = st.columns(3)
                    mpk1.markdown(kpi("Max Pain", f"${mp_result['max_pain_price']:.2f}", "precio de máximo dolor", "blue"), unsafe_allow_html=True)
                    if mp_result.get("current_price"):
                        mpk2.markdown(kpi("Precio Actual", f"${mp_result['current_price']:.2f}", "precio de mercado", "green"), unsafe_allow_html=True)
                        dist = mp_result.get("distance_pct", 0)
                        dist_color = "red" if abs(dist) > 3 else "green"
                        mpk3.markdown(kpi("Distancia", f"{dist:+.1f}%", "del Max Pain", dist_color), unsafe_allow_html=True)

                    # OI por strike (call/put)
                    fig_mp = go.Figure()
                    strikes = mp_result["strikes"]
                    fig_mp.add_trace(go.Bar(
                        x=strikes, y=mp_result["call_oi"],
                        name="Call OI", marker_color="rgba(52,211,153,0.7)"
                    ))
                    fig_mp.add_trace(go.Bar(
                        x=strikes, y=[-v for v in mp_result["put_oi"]],
                        name="Put OI", marker_color="rgba(248,113,113,0.7)"
                    ))
                    fig_mp.add_vline(x=mp_result["max_pain_price"], line_dash="solid",
                                     line_color="#fbbf24", line_width=2,
                                     annotation_text=f"Max Pain: ${mp_result['max_pain_price']:.2f}",
                                     annotation_font_color="#fbbf24")
                    if mp_result.get("current_price"):
                        fig_mp.add_vline(x=mp_result["current_price"], line_dash="dash",
                                         line_color="#60a5fa",
                                         annotation_text=f"Actual: ${mp_result['current_price']:.2f}",
                                         annotation_font_color="#60a5fa")
                    fig_mp.update_layout(
                        **DARK, barmode="overlay", height=450,
                        title=dict(text=f"Open Interest por Strike — {mp_ticker} [{mp_exp}]",
                                   font=dict(color="#94a3b8", size=14), x=0.5),
                        xaxis_title="Strike Price", yaxis_title="Open Interest (Calls + / Puts -)",
                        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"))
                    )
                    st.plotly_chart(fig_mp, use_container_width=True)

                    # Pain curve
                    fig_pain = go.Figure()
                    fig_pain.add_trace(go.Scatter(
                        x=strikes, y=mp_result["total_pain"],
                        mode="lines+markers", line=dict(color="#f87171", width=2.5),
                        fill="tozeroy", fillcolor="rgba(248,113,113,0.08)"
                    ))
                    fig_pain.add_vline(x=mp_result["max_pain_price"], line_dash="dash",
                                       line_color="#fbbf24",
                                       annotation_text=f"Mínimo: ${mp_result['max_pain_price']:.2f}",
                                       annotation_font_color="#fbbf24")
                    fig_pain.update_layout(**DARK, height=300,
                                           title=dict(text="Curva de Dolor Total (menor = Max Pain)",
                                                       font=dict(color="#94a3b8", size=13), x=0.5),
                                           xaxis_title="Strike", yaxis_title="Dolor Total ($)")
                    st.plotly_chart(fig_pain, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 17: SHORT SQUEEZE RADAR
    # ══════════════════════════════════════════════════════════════
    with tab_squeeze:
        wl_sq = db.get_watchlist(portfolio_id=p_id)
        st.markdown("<div class='sec-title'>🔀 Radar de Short Squeeze</div>", unsafe_allow_html=True)
        st.caption("Identifica acciones con alto interés en corto que pueden dispararse violentamente con volumen de compra sostenido.")

        if wl_sq.empty:
            st.info("Agrega tickers a tu watchlist primero.")
        else:
            if st.button("🔍 Escanear Short Interest", type="primary", use_container_width=True, key="sq_run"):
                with st.spinner("Analizando short interest de todos los tickers..."):
                    from utils.short_squeeze import scan_short_squeeze
                    sq_df = scan_short_squeeze(wl_sq["ticker"].tolist())

                if sq_df.empty:
                    st.info("No se obtuvieron datos de short interest. Yahoo Finance puede no tener datos para estos tickers.")
                else:
                    # Top candidates
                    top = sq_df.iloc[0] if len(sq_df) > 0 else None
                    if top is not None:
                        sqk1, sqk2, sqk3, sqk4 = st.columns(4)
                        sqk1.markdown(kpi("Top Candidato", top["ticker"], top["risk_label"], "red"), unsafe_allow_html=True)
                        sqk2.markdown(kpi("Short Float",
                                          f"{top['short_pct_float']}%" if top['short_pct_float'] else "N/A",
                                          "% del float en corto", "red"), unsafe_allow_html=True)
                        sqk3.markdown(kpi("Days to Cover",
                                          f"{top['short_ratio']} días" if top['short_ratio'] else "N/A",
                                          "días para cubrir cortos", "red"), unsafe_allow_html=True)
                        sqk4.markdown(kpi("Squeeze Score", f"{top['squeeze_score']}/100",
                                          "presión acumulada", "red"), unsafe_allow_html=True)

                    # Squeeze Score bar chart
                    fig_sq = go.Figure()
                    colors_sq = ["#f87171" if s >= 60 else ("#fbbf24" if s >= 35 else "#60a5fa")
                                 for s in sq_df["squeeze_score"]]
                    fig_sq.add_trace(go.Bar(
                        x=sq_df["ticker"], y=sq_df["squeeze_score"],
                        marker_color=colors_sq,
                        text=sq_df["risk_label"], textposition="outside",
                        hovertemplate="<b>%{x}</b><br>Score: %{y}<br>%{text}<extra></extra>"
                    ))
                    fig_sq.add_hline(y=50, line_dash="dot", line_color="#fbbf24",
                                     annotation_text="Umbral de Alerta")
                    fig_sq.update_layout(
                        **{k: v for k, v in DARK.items() if k != 'yaxis'},
                        height=400,
                        title=dict(text="Short Squeeze Score por Ticker", font=dict(color="#94a3b8", size=14), x=0.5),
                        xaxis_title="Ticker", 
                        yaxis_title="Squeeze Score (0-100)",
                        yaxis=dict(range=[0, 105])
                    )
                    st.plotly_chart(fig_sq, use_container_width=True)

                    # Table
                    display_sq = sq_df[["ticker", "squeeze_score", "risk_label", "short_pct_float",
                                        "short_ratio", "price"]].copy()
                    display_sq.columns = ["Ticker", "Score", "Riesgo", "Short Float (%)",
                                          "Days to Cover", "Precio"]

                    def _sq_color(val):
                        if isinstance(val, (int, float)) and val >= 60:
                            return "color: #f87171; font-weight: bold"
                        return ""

                    st.dataframe(
                        display_sq.style.map(_sq_color, subset=["Score"]),
                        use_container_width=True, hide_index=True
                    )

    # ══════════════════════════════════════════════════════════════
    # TAB 18: ESTACIONALIDAD HISTÓRICA
    # ══════════════════════════════════════════════════════════════
    with tab_seasonal:
        wl_sea = db.get_watchlist(portfolio_id=p_id)
        st.markdown("<div class='sec-title'>📅 Estacionalidad Histórica</div>", unsafe_allow_html=True)
        st.caption("Patrón estadístico de retornos por mes, día de semana y trimestre. Identifica ventanas de sesgo alcista/bajista recurrente.")

        sc1, sc2, sc3 = st.columns(3)
        sea_ticker = sc1.selectbox("Ticker", wl_sea["ticker"].tolist() if not wl_sea.empty else ["SPY"],
                                   key="sea_tick")
        sea_years = sc2.number_input("Años de historia", value=10, min_value=3, max_value=25, step=1, key="sea_years")
        _ = sc3  # spacer

        if st.button("📅 Calcular Estacionalidad", type="primary", use_container_width=True, key="sea_run"):
            with st.spinner(f"Calculando estacionalidad de {sea_ticker} ({sea_years} años)..."):
                from utils.seasonality import compute_seasonality
                sea_result = compute_seasonality(sea_ticker, years=sea_years)

            if "error" in sea_result:
                st.error(sea_result["error"])
            else:
                sek1, sek2 = st.columns(2)
                sek1.markdown(kpi("Mejor Mes", sea_result["best_month"], "retorno promedio más alto", "green"), unsafe_allow_html=True)
                sek2.markdown(kpi("Peor Mes", sea_result["worst_month"], "retorno promedio más bajo", "red"), unsafe_allow_html=True)

                # Monthly heatmap bar chart
                monthly = sea_result["monthly"]
                bar_colors = ["#34d399" if r >= 0 else "#f87171" for r in monthly["Retorno Promedio (%)"]]
                fig_month = go.Figure()
                fig_month.add_trace(go.Bar(
                    x=monthly["Mes"], y=monthly["Retorno Promedio (%)"],
                    marker_color=bar_colors,
                    text=[f"{v:+.1f}%" for v in monthly["Retorno Promedio (%)"]],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Retorno: %{y:.2f}%<br>Win Rate: %{customdata:.1f}%<extra></extra>",
                    customdata=monthly["Win Rate (%)"]
                ))
                fig_month.add_hline(y=0, line_dash="solid", line_color="#475569")
                fig_month.update_layout(**DARK, height=380,
                                         title=dict(text=f"Retorno Promedio Mensual — {sea_ticker} ({sea_years}a)",
                                                     font=dict(color="#94a3b8", size=14), x=0.5),
                                         xaxis_title="Mes", yaxis_title="Retorno Promedio (%)")
                st.plotly_chart(fig_month, use_container_width=True)

                # Win rate heatmap
                fig_wr = go.Figure(go.Heatmap(
                    z=[monthly["Win Rate (%)"].tolist()],
                    x=monthly["Mes"].tolist(),
                    y=["Win Rate"],
                    colorscale=[[0, "#f87171"], [0.5, "#fbbf24"], [1, "#34d399"]],
                    zmin=0, zmax=100,
                    text=[[f"{v:.0f}%" for v in monthly["Win Rate (%)"]]],
                    texttemplate="%{text}",
                    hovertemplate="Mes: %{x}<br>Win Rate: %{z:.1f}%<extra></extra>",
                    colorbar=dict(title="Win Rate %", tickfont=dict(color="#94a3b8"), titlefont=dict(color="#94a3b8"))
                ))
                fig_wr.update_layout(**DARK, height=140,
                                      title=dict(text="Win Rate Mensual (%)", font=dict(color="#94a3b8", size=13), x=0.5))
                st.plotly_chart(fig_wr, use_container_width=True)

                # Day of week
                weekly = sea_result["weekly"]
                dw_colors = ["#34d399" if r >= 0 else "#f87171" for r in weekly["Retorno Promedio (%)"]]
                fig_dw = go.Figure(go.Bar(
                    x=weekly["Día"], y=weekly["Retorno Promedio (%)"],
                    marker_color=dw_colors,
                    text=[f"{v:+.3f}%" for v in weekly["Retorno Promedio (%)"]],
                    textposition="outside"
                ))
                fig_dw.add_hline(y=0, line_dash="solid", line_color="#475569")
                fig_dw.update_layout(**DARK, height=320,
                                      title=dict(text="Retorno Promedio por Día de Semana",
                                                  font=dict(color="#94a3b8", size=13), x=0.5),
                                      xaxis_title="Día", yaxis_title="Retorno Diario Promedio (%)")
                st.plotly_chart(fig_dw, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 19: PAIRS TRADING
    # ══════════════════════════════════════════════════════════════
    with tab_pairs:
        wl_pt = db.get_watchlist(portfolio_id=p_id)
        st.markdown("<div class='sec-title'>🔗 Pairs Trading — Arbitraje Estadístico</div>", unsafe_allow_html=True)
        st.caption("Test de cointegración de Engle-Granger para identificar pares de activos con correlación mean-reverting y generar señales de spread.")

        if wl_pt.empty or len(wl_pt) < 2:
            st.info("Necesitas al menos 2 tickers en tu watchlist para el análisis de pares.")
        else:
            pt_period = st.selectbox("Período de análisis", ["6mo", "1y", "2y"], index=1, key="pt_period")

            if st.button("🔬 Escanear Pares Cointegrados", type="primary", use_container_width=True, key="pt_run"):
                with st.spinner("Ejecutando test de cointegración..."):
                    from utils.pairs_trading import compute_pairs_analysis
                    pt_result = compute_pairs_analysis(wl_pt["ticker"].tolist(), period=pt_period)

                if "error" in pt_result:
                    st.error(pt_result["error"])
                else:
                    pairs_df = pt_result["pairs"]
                    coint_list = pt_result["cointegrated"]

                    ptk1, ptk2 = st.columns(2)
                    ptk1.markdown(kpi("Pares analizados", str(len(pairs_df)), "combinaciones", "blue"), unsafe_allow_html=True)
                    ptk2.markdown(kpi("Cointegrados (p<0.05)", str(len(coint_list)), "pares estadísticos", "green"), unsafe_allow_html=True)

                    def _coint_color(val):
                        if val == "✅": return "color: #34d399"
                        if val == "❌": return "color: #f87171"
                        return ""

                    st.dataframe(
                        pairs_df.style.map(_coint_color, subset=["Cointegrado"]).format({"P-Value": "{:.4f}"}),
                        use_container_width=True, hide_index=True, height=300
                    )

                    # Allow spread drill-down for cointegrated pairs
                    if coint_list:
                        st.markdown("---")
                        st.markdown("**Análisis de Spread para un par cointegrado:**")
                        pair_options = [f"{t1} / {t2}" for t1, t2 in coint_list]
                        selected_pair = st.selectbox("Seleccionar par", pair_options, key="pt_pair_sel")
                        t1, t2 = [x.strip() for x in selected_pair.split("/")]

                        if st.button(f"📊 Ver Spread: {t1} / {t2}", key="pt_spread_run"):
                            with st.spinner("Calculando spread y Z-score..."):
                                from utils.pairs_trading import get_spread_analysis
                                spread_result = get_spread_analysis(t1, t2, period=pt_period)

                            if "error" in spread_result:
                                st.error(spread_result["error"])
                            else:
                                st.markdown(f"<div style='background:rgba(96,165,250,0.1);border:1px solid #60a5fa;"
                                            f"padding:12px;border-radius:8px;text-align:center;font-size:16px;'>"
                                            f"<b>Señal Actual:</b> {spread_result['signal']}</div>",
                                            unsafe_allow_html=True)

                                fig_spread = go.Figure()
                                spread = spread_result["spread"]
                                fig_spread.add_trace(go.Scatter(x=spread.index, y=spread.values,
                                                                mode="lines", line=dict(color="#60a5fa", width=1.5),
                                                                name="Spread"))
                                fig_spread.add_hline(y=spread.mean(), line_dash="dash", line_color="#fbbf24",
                                                     annotation_text="Media")
                                fig_spread.update_layout(**DARK, height=280,
                                                         title=dict(text=f"Spread: {t1} - {spread_result['hedge_ratio']:.2f}×{t2}",
                                                                     font=dict(color="#94a3b8", size=13), x=0.5))
                                st.plotly_chart(fig_spread, use_container_width=True)

                                zscore = spread_result["z_score"].dropna()
                                fig_z = go.Figure()
                                fig_z.add_trace(go.Scatter(x=zscore.index, y=zscore.values,
                                                           mode="lines", line=dict(color="#a78bfa", width=1.5),
                                                           name="Z-Score", fill="tozeroy",
                                                           fillcolor="rgba(167,139,250,0.08)"))
                                fig_z.add_hline(y=2,  line_dash="dot", line_color="#f87171",
                                                annotation_text="Short Signal (+2σ)")
                                fig_z.add_hline(y=-2, line_dash="dot", line_color="#34d399",
                                                annotation_text="Long Signal (-2σ)")
                                fig_z.add_hline(y=0,  line_dash="solid", line_color="#475569")
                                fig_z.update_layout(**DARK, height=280,
                                                    title=dict(text="Z-Score del Spread (±2σ = señal)",
                                                                font=dict(color="#94a3b8", size=13), x=0.5),
                                                    yaxis_title="Z-Score")
                                st.plotly_chart(fig_z, use_container_width=True)
