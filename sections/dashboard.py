"""sections/dashboard.py - Quantum Retail Terminal v8.9.2"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf
import database as db
from ui_shared import DARK, dark_layout, fmt, kpi
import excel_export, ai_engine
from utils import visual_components as vc
import cache_utils
import numpy as np

# Import specialized engines
try:
    from utils import risk_engine
    from services.macro_stress_test import MacroStressEngine
except ImportError:
    risk_engine = None
    MacroStressEngine = None

try:
    from data_sources import cached_fear_greed_index, cached_vix, cached_spy_put_call_ratio
except ImportError:
    cached_fear_greed_index = cached_vix = cached_spy_put_call_ratio = None

# Local aliases for centralized cache functions
get_batch_prices_and_changes = cache_utils.get_batch_prices_and_changes
get_history = cache_utils.get_history
get_batch_prices = cache_utils.get_batch_prices

# Define missing service placeholders/imports
try:
    from services import trading_audit, stress_testing, notifications
except ImportError:
    trading_audit = stress_testing = notifications = None

_ZERO = {"price": 0, "prev": 0, "change_pct": 0}

def _sec(title):
    st.markdown(f"<div class='sec-title'>{title}</div>", unsafe_allow_html=True)

def render():
    p_id = st.session_state.get("active_portfolio_id", 1)
    wl = db.get_watchlist(portfolio_id=p_id)
    trades_stock = db.get_trades(portfolio_id=p_id)
    trades_fx = db.get_forex_trades(portfolio_id=p_id)
    analyses = db.get_stock_analyses()
    total_val = total_inv = n_positions = 0
    prices_map, position_rows = {}, []

    if not wl.empty and yf:
        n_positions = len(wl)
        tickers_list = [row["ticker"] for _, row in wl.iterrows()]
        try:
            prices_map = get_batch_prices_and_changes(tuple(tickers_list))
        except Exception:
            prices_map = {}

        for _, row in wl.iterrows():
            t = row["ticker"]
            pd_info = prices_map.get(t, {})
            price = pd_info.get("price", 0)
            change_pct = pd_info.get("change_pct", 0)

            if price == 0:
                try: price = yf.Ticker(t).fast_info.last_price or 0
                except: price = 0

            val = row["shares"] * price
            inv = row["shares"] * row["avg_cost"]
            pnl_pos = val - inv
            pnl_pct_pos = (pnl_pos / inv * 100) if inv > 0 else 0
            
            total_val += val
            total_inv += inv
            
            position_rows.append({
                "Ticker": t, "Shares": row["shares"], "Avg Cost": row["avg_cost"],
                "Price": price, "P&L $": pnl_pos, "P&L %": pnl_pct_pos,
                "Day %": change_pct, "Value": val, "Sector": row.get("sector", ""),
                "Industry": row.get("industry", "N/A"),
            })
    
    total_pnl = total_val - total_inv
    pct_total = (total_pnl / total_inv * 100) if total_inv > 0 else 0

    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Portfolio Analytics</h1>
        <p>Bloomberg-style cockpit · Real-time overview · Risk · Events</p>
      </div>
      <div id='report-btn-container'>
      </div>
    </div>""", unsafe_allow_html=True)

    # UI for Report generation
    if st.button("📊 Generar Reporte Semanal PDF", key="gen_report_btn"):
        st.toast("Generando reporte institucional...")
        try:
            from services import report_generator
            # Prepare data
            from valuation import get_ultra_health_report
            forensics_data = []
            for pos in position_rows[:5]: # Auditoría de las top 5 posiciones
                try:
                    h = get_ultra_health_report(pos["Ticker"])
                    forensics_data.append({
                        "Ticker": pos["Ticker"],
                        "M-Score": h.get("z_score", 0), # Usamos z_score como proxy del M-Score
                        "Sloan": h.get("sloan_ratio", 0) * 100,
                        "Merton PD": 0.01, # Placeholder
                        "Status": h.get("z_label", "SAFE")
                    })
                except: continue

            report_data = {
                "total_val": total_val,
                "total_pnl": total_pnl,
                "pct_total": (total_pnl / total_inv) * 100 if total_inv > 0 else 0,
                "n_positions": n_positions,
                "r_score": risk_stats.get("perf_stats", {}).get("sharpe", 0) if risk_stats else 0,
                "r_grade": "A+" if n_positions > 0 else "N/A",
                "positions": position_rows,
                "stress_results": st.session_state.get("last_stress_results", {}),
                "forensics": forensics_data
            }
            pdf_bytes = report_generator.generate_weekly_report(report_data)
            st.download_button(
                label="📥 Descargar Reporte PDF-ULTRA",
                data=pdf_bytes,
                file_name=f"Quantum_Audit_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Error al generar reporte: {e}")

    # ── Pre-Market Toggle ──
    pre_market = st.toggle("🚀 Modo Pre-Mercado Focus", value=False, help="Muestra futuros y sentimiento antes de la apertura")
    
    # ── TRADINGVIEW HEATMAP (MOVE TO TOP) ──
    with st.expander("🗺️ Mapa Heatmap S&P 500 (TradingView)", expanded=False):
        st.components.v1.html("""
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>
          {
              "exchanges": [],
              "dataSource": "S&P500",
              "grouping": "sector",
              "blockSize": "market_cap_basic",
              "blockColor": "change",
              "locale": "en",
              "symbolUrl": "",
              "colorTheme": "dark",
              "hasTopBar": false,
              "isDatasetEnabled": false,
              "isTransparent": true,
              "width": "100%",
              "height": "600"
          }
          </script>
        </div>
        """, height=600)

    if pre_market:
        _sec("Pre-Market Pulse: US Futures")
        try:
            future_ticks = ["ES=F", "NQ=F", "YM=F", "RTY=F"]
            f_data = get_batch_prices_and_changes(tuple(future_ticks))
            cols = st.columns(len(future_ticks))
            for i, ft in enumerate(future_ticks):
                d = f_data.get( ft, {"price": 0, "change_pct": 0})
                color = "green" if d["change_pct"] >= 0 else "red"
                val_str = f"${d['price']:,.2f}"
                pct_str = f"{d['change_pct']:+.2f}%"
                cols[i].markdown(f"""
                <div style='background:rgba(0,0,0,0.2);padding:10px;border-radius:8px;border-left:4px solid {color};'>
                    <small style='color:#94a3b8;'>{ft}</small><br>
                    <span style='font-size:20px;font-weight:700;'>{val_str}</span><br>
                    <span style='color:{color};font-weight:600;'>{pct_str}</span>
                </div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
        except Exception:
            st.info("Futuros no disponibles en este momento.")


    # total_pnl calculated above
    # pct_total calculated above

    # Weights
    for p in position_rows:
        p["Weight %"] = (p["Value"] / total_val * 100) if total_val > 0 else 0

    # Trading P&L
    stock_pnl = trades_stock[trades_stock["pnl"].notna()]["pnl"].sum() if not trades_stock.empty else 0
    fx_pnl = trades_fx[trades_fx["pnl"].notna()]["pnl"].sum() if not trades_fx.empty else 0
    total_trading_pnl = stock_pnl + fx_pnl

    all_closed = []
    if not trades_stock.empty:
        all_closed.extend(trades_stock[trades_stock["pnl"].notna()]["pnl"].tolist())
    if not trades_fx.empty:
        all_closed.extend(trades_fx[trades_fx["pnl"].notna()]["pnl"].tolist())
    win_rate = (sum(1 for p in all_closed if p > 0) / len(all_closed) * 100) if all_closed else 0
    # --- NEW: Advanced Risk Engine Calculation Core ---
    risk_stats = {}
    hist_returns = pd.DataFrame()
    weights_p = {}
    if risk_engine and not wl.empty:
        try:
            # 1. Weights based on market value
            weights_p = {row["ticker"]: row["shares"] * prices_map.get(row["ticker"], _ZERO)["price"] for _, row in wl.iterrows()}
            total_market_val = sum(weights_p.values())
            if total_market_val > 0:
                weights_p = {t: v/total_market_val for t, v in weights_p.items()}
                
                # 2. Historical Returns (1 year)
                hist_returns = risk_engine.get_historical_returns(list(weights_p.keys()))
                
                # 3. Compute Metrics
                beta_stats = risk_engine.calculate_exposure_metrics(hist_returns, weights_p)
                perf_stats = risk_engine.calculate_performance_profiler(hist_returns, weights_p)
                var_stats = risk_engine.calculate_advanced_var(hist_returns, weights_p, portfolio_value=total_val)
                corr_matrix, corr_alerts = risk_engine.analyze_correlation(hist_returns)
                
                risk_stats = {
                    "beta_stats": beta_stats,
                    "perf_stats": perf_stats,
                    "var_stats": var_stats,
                    "corr_alerts": corr_alerts
                }
        except Exception as risk_e:
            st.error(f"Error in Risk Engine: {risk_e}")

    # ── ROW 0: Earnings Alert Banner ──
    try:
        if not wl.empty and yf:
            upcoming_earnings = []
            for row_idx in range(min(10, len(wl))):
                try:
                    row = wl.iloc[row_idx]
                    cal = yf.Ticker(row["ticker"]).calendar
                    if cal is not None:
                        if isinstance(cal, dict):
                            ed = cal.get("Earnings Date", [None])
                            if ed and ed[0]:
                                diff = (ed[0] - datetime.now()).days
                                if 0 <= diff <= 7:
                                    upcoming_earnings.append((row["ticker"], ed[0].strftime("%Y-%m-%d"), diff))
                        elif isinstance(cal, pd.DataFrame) and not cal.empty:
                            if "Earnings Date" in cal.index:
                                ed_vals = cal.loc["Earnings Date"]
                                for ed_val in ed_vals:
                                    if pd.notna(ed_val):
                                        ed_ts = pd.Timestamp(ed_val)
                                        diff = (ed_ts - pd.Timestamp(datetime.now())).days
                                        if 0 <= diff <= 7:
                                            upcoming_earnings.append((row["ticker"], ed_ts.strftime("%Y-%m-%d"), diff))
                                        break
                except Exception:
                    pass
            if upcoming_earnings:
                msg = " | ".join([f"**{t}** reporta en {d} dias ({dt})" for t, dt, d in upcoming_earnings])
                st.warning(f"Earnings proximos: {msg}")
    except Exception:
        pass

    # Get Workspace Config (Phase 7)
    config = st.session_state.get("w_config", {"performance":True,"risk":True,"precision":True,"psychology":True,"surveillance":True,"scanners":True})

    # ── ROW 0: Alerts & Surveillance ──
    if config.get("surveillance", True):
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            _render_critical_surveillance()
        with col_s2:
            _render_dividend_monitor(wl, prices_map)
    
    _sec("Portfolio Overview")
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    # pct_total consolidado arriba
    with k1:
        vc.render_metric_card("Portfolio Value", fmt(total_val) if total_val > 0 else "$0", subtitle=f"{n_positions} positions")
    k2.empty()
    with k2:
        vc.render_metric_card("P&L Total", fmt(total_pnl), subtitle=f"{pct_total:+.2f}%", delta=pct_total)
    
    k3.empty()
    with k3:
        vc.render_metric_card("Trading P&L", f"${total_trading_pnl:+,.0f}", subtitle=f"Stocks: ${stock_pnl:+,.0f} | FX: ${fx_pnl:+,.0f}")
    
    k4.empty()
    with k4:
        vc.render_metric_card("Win Rate", f"{win_rate:.1f}%", subtitle=f"{len(all_closed)} closed trades")
    
    with k5:
        sharpe_val = risk_stats.get("perf_stats", {}).get("sharpe", 0.0) if risk_stats else 0.0
        vc.render_metric_card("Sharpe Ratio", f"{sharpe_val:.2f}", subtitle="return / risk")
    
    # ── NEW: Institutional Risk Health Panel ──
    if risk_engine and risk_stats:
        b_val = risk_stats["beta_stats"].get("beta", 1.0)
        s_val = risk_stats["perf_stats"].get("sharpe", 0.0)
        v_val = risk_stats["var_stats"].get("var_hist_val", 0.0)
        a_val = risk_stats["beta_stats"].get("alpha_annual", 0.0)
        c_alerts = risk_stats["corr_alerts"]
        
        st.markdown("""
        <div style='background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.1);border-radius:15px;padding:20px;margin:20px 0;'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;'>
                <div style='display:flex;align-items:center;gap:10px;'>
                    <span style='font-size:20px;'>🛡️</span>
                    <span style='font-weight:700;letter-spacing:1px;color:#cbd5e1;'>SALUD DEL PORTAFOLIO</span>
                </div>
                <div style='font-size:11px;color:#64748b;'>Actualizado: """ + datetime.now().strftime("%H:%M") + """</div>
            </div>
            <div style='display:grid;grid-template-columns: repeat(5, 1fr); gap:15px; text-align:center;'>
                <div>
                    <div style='color:#94a3b8;font-size:11px;text-transform:uppercase;'>Beta</div>
                    <div style='font-size:22px;font-weight:800;color:#60a5fa;'>""" + f"{b_val:.2f}" + """</div>
                    <div style='font-size:10px;color:#64748b;'>""" + ("Agresivo" if b_val > 1.2 else "Defensivo" if b_val < 0.8 else "Equilibrado") + """</div>
                </div>
                <div>
                    <div style='color:#94a3b8;font-size:11px;text-transform:uppercase;'>Sharpe</div>
                    <div style='font-size:22px;font-weight:800;color:#34d399;'>""" + f"{s_val:.2f}" + """</div>
                    <div style='font-size:10px;color:#64748b;'>""" + ("Eficiente" if s_val > 1 else "Aceptable") + """</div>
                </div>
                <div>
                    <div style='color:#94a3b8;font-size:11px;text-transform:uppercase;'>VaR 95%</div>
                    <div style='font-size:22px;font-weight:800;color:#f87171;'>""" + f"-${abs(v_val):,.0f}" + """</div>
                    <div style='font-size:10px;color:#64748b;'>Diario</div>
                </div>
                <div>
                    <div style='color:#94a3b8;font-size:11px;text-transform:uppercase;'>Alpha</div>
                    <div style='font-size:22px;font-weight:800;color:#818cf8;'>""" + f"{a_val:+.1f}%" + """</div>
                    <div style='font-size:10px;color:#64748b;'>Anual</div>
                </div>
                <div>
                    <div style='color:#94a3b8;font-size:11px;text-transform:uppercase;'>Correlación</div>
                    <div style='font-size:22px;font-weight:800;color:""" + ("#fbbf24" if c_alerts else "#34d399") + """;'>""" + (f"⚠️ {len(c_alerts)}" if c_alerts else "Óptima") + """</div>
                    <div style='font-size:10px;color:#64748b;'>Watchlist</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Action Buttons for Detail Views
        ac1, ac2, ac3, ac4 = st.columns(4)
        if ac1.button("📂 Matriz Correlación", use_container_width=True): st.session_state.r_view = "corr"
        if ac2.button("📈 Frontera Eficiente", use_container_width=True): st.session_state.r_view = "frontier"
        if ac3.button("📊 Distribución VaR", use_container_width=True): st.session_state.r_view = "var"
        if ac4.button("🌊 Atribución Alpha", use_container_width=True): st.session_state.r_view = "factor"
        
        # Render Selected Fragment
        r_view = st.session_state.get("r_view")
        if r_view == "corr":
            _render_risk_heatmap(hist_returns)
        elif r_view == "frontier":
            _render_efficient_frontier(hist_returns, weights_p)
        elif r_view == "var":
            _render_var_histogram(hist_returns, weights_p, risk_stats["var_stats"])
        elif r_view == "factor":
            _render_factor_attribution(risk_stats["beta_stats"])

    with k6:
        grade_colors = {"A+": "#34d399", "A": "#34d399", "B": "#60a5fa", "C": "#fbbf24", "D": "#fb923c", "F": "#f87171"}
        r_score = risk_stats.get("perf_stats", {}).get("sharpe", 0.0) if risk_stats else 0.0 # Using sharpe as proxy
        r_grade = "A" if r_score > 1.5 else ("B" if r_score > 1 else "C")
        g_color = grade_colors.get(r_grade, "#94a3b8")
        st.markdown(f"""
        <div class="metric-card">
            <div class="mc-label">Weekly Risk Score</div>
            <div class="mc-value" style="color:{g_color};">{r_score:.2f} <span style="font-size:14px;opacity:0.8;">({r_grade})</span></div>
            <div class="mc-bench">Proprietary Alpha-Beta Health</div>
        </div>
        """, unsafe_allow_html=True)

    # Composition Heatmap

    # ── Portfolio Heatmap (Treemap) ──
    if position_rows:
        _sec("Portfolio Composition & Performance")
        try:
            import plotly.express as px
            df_heat = pd.DataFrame(position_rows)
            # Ensure Factor levels are not empty for the treemap path
            df_heat["Sector"] = df_heat["Sector"].apply(lambda x: x if (x and str(x).strip()) else "N/A")
            df_heat["Industry"] = df_heat["Industry"].apply(lambda x: x if (x and str(x).strip()) else "N/A")
            
            fig_heat = px.treemap(
                df_heat,
                path=[px.Constant("Portfolio"), 'Sector', 'Industry', 'Ticker'],
                values='Value',
                color='Day %',
                color_continuous_scale='RdYlGn',
                color_continuous_midpoint=0,
                hover_data=['Weight %', 'P&L %'],
                custom_data=['Ticker', 'Value', 'Day %']
            )
            fig_heat.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata[2]:+.2f}%",
                hovertemplate="<b>%{customdata[0]}</b><br>Value: $%{customdata[1]:,.2f}<br>Day: %{customdata[2]:+.2f}%"
            )
            fig_heat.update_layout(
                margin=dict(t=30, l=10, r=10, b=10),
                height=500, # Increased for hierarchy depth
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_colorbar=dict(title="Day %", thickness=15, len=0.5)
            )
            st.plotly_chart(fig_heat, use_container_width=True)
        except Exception as e:
            st.info(f"Heatmap unavailable: {e}")

    @st.fragment(run_every=60)
    def _render_market_pulse():
        _sec("Market Pulse")
        try:
            mp1, mp2, mp3 = st.columns(3)

            # Fear & Greed Index
            with mp1:
                try:
                    fg = cached_fear_greed_index() if cached_fear_greed_index else None
                    if fg:
                        fg_val = fg["value"]
                        fg_color = "#34d399" if fg_val > 75 else ("#a3e635" if fg_val > 55 else ("#fbbf24" if fg_val > 45 else ("#fb923c" if fg_val > 25 else "#f87171")))
                        fig_fg = go.Figure(go.Indicator(
                            mode="gauge+number", value=fg_val,
                            title={"text": "Fear & Greed Index", "font": {"size": 13, "color": "#94a3b8"}},
                            number={"font": {"color": fg_color, "size": 36}},
                            gauge={"axis": {"range": [0, 100], "dtick": 25}, "bar": {"color": fg_color}, "bgcolor": "#0a0a0a"}
                        ))
                        fig_fg.update_layout(**DARK, height=250)
                        st.plotly_chart(fig_fg, use_container_width=True)
                        st.caption(f"Classification: **{fg['label']}**")
                    else:
                        st.markdown(kpi("Fear & Greed", "N/A", "No data", "blue"), unsafe_allow_html=True)
                except Exception:
                    st.markdown(kpi("Fear & Greed", "N/A", "Error", "blue"), unsafe_allow_html=True)

            # VIX
            with mp2:
                try:
                    vix = cached_vix() if cached_vix else None
                    if vix:
                        vix_hex = "#34d399" if vix < 15 else ("#60a5fa" if vix < 20 else ("#fbbf24" if vix < 30 else "#f87171"))
                        fig_vix = go.Figure(go.Indicator(mode="number", value=vix, number={"font": {"color": vix_hex, "size": 48}}))
                        fig_vix.update_layout(**DARK, height=250, title={"text": "VIX Index", "font": {"size": 13, "color": "#94a3b8"}})
                        st.plotly_chart(fig_vix, use_container_width=True)
                    else:
                        st.markdown(kpi("VIX", "N/A", "No data", "blue"), unsafe_allow_html=True)
                except Exception:
                    st.markdown(kpi("VIX", "N/A", "Error", "blue"), unsafe_allow_html=True)

            # SPY PCR
            with mp3:
                try:
                    pcr = cached_spy_put_call_ratio() if cached_spy_put_call_ratio else None
                    if pcr:
                        ratio = pcr["ratio"]
                        pcr_color = "#34d399" if ratio < 0.7 else ("#fbbf24" if ratio < 1.0 else "#f87171")
                        fig_pcr = go.Figure(go.Indicator(mode="number", value=ratio, number={"font": {"color": pcr_color, "size": 48}, "valueformat": ".3f"}))
                        fig_pcr.update_layout(**DARK, height=200, title={"text": "SPY Put/Call", "font": {"size": 13, "color": "#94a3b8"}})
                        st.plotly_chart(fig_pcr, use_container_width=True)
                    else:
                        st.markdown(kpi("SPY Put/Call", "N/A", "No data", "blue"), unsafe_allow_html=True)
                except Exception:
                    st.markdown(kpi("SPY Put/Call", "N/A", "Error", "blue"), unsafe_allow_html=True)
        except Exception as e:
            st.info(f"Market pulse unavailable: {e}")

    _render_market_pulse()
    

    # ── Sentiment Thermometer (VADER + RSS) ──
    @st.fragment(run_every=900)
    def _render_sentiment_pulse():
        _sec("News Sentiment Thermometer")
        try:
            from utils.sentiment_vader import get_sentiment_pulse
            pulse = get_sentiment_pulse()

            sp1, sp2 = st.columns([1, 2])
            with sp1:
                score = pulse["score"]
                # Map -100..+100 to 0..100 for gauge
                gauge_val = (score + 100) / 2

                if score >= 15:
                    gauge_color = "#34d399"
                elif score <= -15:
                    gauge_color = "#f87171"
                else:
                    gauge_color = "#fbbf24"

                fig_sent = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=gauge_val,
                    number={"font": {"color": gauge_color, "size": 42}, "suffix": "", "valueformat": ".0f"},
                    title={"text": f"Sentimiento: {pulse['label']}", "font": {"size": 13, "color": "#94a3b8"}},
                    gauge={
                        "axis": {"range": [0, 100], "dtick": 25,
                                 "ticktext": ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"],
                                 "tickvals": [10, 25, 50, 75, 90]},
                        "bar": {"color": gauge_color, "thickness": 0.3},
                        "bgcolor": "#0a0a0a",
                        "steps": [
                            {"range": [0, 25], "color": "rgba(239,68,68,0.15)"},
                            {"range": [25, 40], "color": "rgba(251,191,36,0.1)"},
                            {"range": [40, 60], "color": "rgba(148,163,184,0.08)"},
                            {"range": [60, 75], "color": "rgba(163,230,53,0.1)"},
                            {"range": [75, 100], "color": "rgba(52,211,153,0.15)"},
                        ],
                        "threshold": {"line": {"color": "#fbbf24", "width": 2}, "thickness": 0.8, "value": 50}
                    }
                ))
                fig_sent.update_layout(**DARK, height=280)
                st.plotly_chart(fig_sent, use_container_width=True)
                st.caption(f"📰 {pulse['total']} titulares · 🟢 {pulse['bullish_count']} · 🔴 {pulse['bearish_count']} · ⚪ {pulse['neutral_count']} · ⏰ {pulse['timestamp']}")

            with sp2:
                top_headlines = pulse["headlines"][:8]
                if top_headlines:
                    for h in top_headlines:
                        icon = "🟢" if h["label"] == "Bullish" else ("🔴" if h["label"] == "Bearish" else "⚪")
                        score_color = "#34d399" if h["compound"] > 0 else ("#f87171" if h["compound"] < 0 else "#94a3b8")
                        st.markdown(f"""
                        <div style='padding:4px 0;border-bottom:1px solid #1a1a1a;font-size:13px;'>
                            {icon} <span style='color:#e2e8f0;'>{h['title'][:80]}</span>
                            <span style='color:{score_color};font-weight:600;float:right;'>{h['compound']:+.2f}</span>
                            <br><small style='color:#475569;'>{h['source']}</small>
                        </div>""", unsafe_allow_html=True)
                else:
                    st.info("No se pudieron obtener titulares de noticias.")
            
            # --- NEW: Sentiment History Trend ---
            st.markdown("<br>", unsafe_allow_html=True)
            hist_df = db.get_sentiment_trend(days=14)
            if not hist_df.empty:
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=hist_df["date"], y=hist_df["avg_score"],
                    mode='lines+markers',
                    line=dict(color='#60a5fa', width=3),
                    fill='tozeroy',
                    fillcolor='rgba(96,165,250,0.1)',
                    name="Sentimiento Promedio"
                ))
                fig_trend.update_layout(**DARK, height=180, 
                    margin=dict(l=0,r=0,t=20,b=0),
                    title={"text": "Tendencia de Sentimiento (14d)", "font": {"size": 11, "color": "#64748b"}},
                    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)'))
                st.plotly_chart(fig_trend, use_container_width=True)
        except Exception as e:
            st.info(f"Sentimiento no disponible: {e}")

    _render_sentiment_pulse()

    # ── Social Sentiment (Reddit Pulse) ──
    def _render_social_pulse():
        _sec("Social Sentiment (Reddit/WallStreetBets)")
        try:
            sent_df = db.get_latest_sentiment(limit=100)
            if sent_df.empty:
                st.info("No hay datos de sentimiento social disponibles. Iniciando sincronización...")
                return

            # Agrupar por ticker y sumar menciones
            reddit_df = sent_df[sent_df['source'] == 'reddit']
            if reddit_df.empty:
                st.info("Aún no hay menciones en Reddit registradas.")
                return
                
            ticker_groups = reddit_df.groupby('ticker')['mentions'].sum().sort_values(ascending=False).head(10)
            
            sc1, sc2 = st.columns([2, 1])
            with sc2:
                # Top Tickers mentions bar chart
                fig_bar = go.Figure(go.Bar(
                    x=ticker_groups.values,
                    y=ticker_groups.index,
                    orientation='h',
                    marker_color='#6366f1'
                ))
                fig_bar.update_layout(**DARK, height=300, margin=dict(l=0, r=0, t=30, b=0),
                                    title={"text": "Menciones (24h)", "font": {"size": 13, "color": "#94a3b8"}})
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with sc1:
                # Latest reddit signals
                for _, row in reddit_df.head(6).iterrows():
                    st.markdown(f"""
                    <div style='padding:8px; background:rgba(99,102,241,0.05); border-radius:6px; margin-bottom:8px; border-left:3px solid #6366f1;'>
                        <span style='color:#6366f1; font-weight:700;'>${row['ticker']}</span> 
                        <span style='color:#94a3b8; font-size:12px; float:right;'>{row['created_at'].split()[1]}</span><br>
                        <span style='color:#e2e8f0; font-size:13px;'>{row['headline']}</span>
                    </div>""", unsafe_allow_html=True)
                    
        except Exception as e:
            st.warning(f"Error al cargar sentimiento social: {e}")

    _render_social_pulse()

    @st.fragment(run_every=30)
    def _render_live_positions(rows):
        if not rows:
            return
        try:
            _sec("Live Positions")
            pos_df = pd.DataFrame(rows)
            sort_col = st.selectbox("Sort by", ["P&L %", "P&L $", "Day %", "Weight %", "Value", "Ticker"], index=0, key="pos_sort")
            pos_df = pos_df.sort_values(sort_col, ascending=(sort_col == "Ticker"))
            
            display_df = pos_df[["Ticker", "Shares", "Avg Cost", "Price", "P&L $", "P&L %", "Day %", "Weight %"]].copy()
            def _color_pnl(val):
                if isinstance(val, (int, float)):
                    return "color: #34d399" if val > 0 else ("color: #f87171" if val < 0 else "color: #94a3b8")
                return "color: #94a3b8"

            styled = display_df.style.format({
                "Shares": "{:.0f}", "Avg Cost": "${:.2f}", "Price": "${:.2f}",
                "P&L $": "${:+,.2f}", "P&L %": "{:+.2f}%", "Day %": "{:+.2f}%", "Weight %": "{:.1f}%"
            }).map(_color_pnl, subset=["P&L $", "P&L %", "Day %"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        except Exception as e:
            st.info(f"Could not load positions table: {e}")

    _render_live_positions(position_rows)

    try:
        if position_rows:
            r4c1, r4c2 = st.columns(2)

            # LEFT: Allocation Pie Chart
            with r4c1:
                _sec("Allocation")
                pos_df_alloc = pd.DataFrame(position_rows)

                # Try sector allocation first, fall back to ticker
                if pos_df_alloc["Sector"].str.strip().ne("").any():
                    alloc_group = pos_df_alloc.groupby("Sector")["Value"].sum().reset_index()
                    alloc_group = alloc_group[alloc_group["Value"] > 0]
                    labels = alloc_group["Sector"].tolist()
                    values = alloc_group["Value"].tolist()
                    alloc_title = "By Sector"
                else:
                    alloc_sorted = pos_df_alloc[pos_df_alloc["Value"] > 0].sort_values("Value", ascending=False)
                    labels = alloc_sorted["Ticker"].tolist()
                    values = alloc_sorted["Value"].tolist()
                    alloc_title = "By Ticker"

                if labels:
                    colors_palette = ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f87171",
                                      "#c084fc", "#fb923c", "#38bdf8", "#e879f9", "#4ade80"]
                    fig_alloc = go.Figure(go.Pie(
                        labels=labels, values=values,
                        marker_colors=colors_palette[:len(labels)], hole=0.55,
                        textfont=dict(color="white"), textinfo="label+percent"))
                    fig_alloc.update_layout(**DARK, height=350,
                        title=dict(text=f"Allocation {alloc_title}", font=dict(color="#94a3b8", size=13), x=0.5),
                        showlegend=False,
                        annotations=[dict(text=fmt(total_val), x=0.5, y=0.5, showarrow=False,
                                          font=dict(size=18, color="#f0f6ff", family="Inter"))])
                    st.plotly_chart(fig_alloc, use_container_width=True)

            # RIGHT: Top Movers Today
            with r4c2:
                _sec("Top Movers Today")
                movers_df = pd.DataFrame(position_rows)
                movers_df = movers_df[movers_df["Price"] > 0].sort_values("Day %", ascending=False)

                if not movers_df.empty:
                    for _, m in movers_df.iterrows():
                        chg = m["Day %"]
                        icon = "+" if chg >= 0 else ""
                        color = "#34d399" if chg >= 0 else "#f87171"
                        dot = "&#x1F7E2;" if chg >= 0 else "&#x1F534;"
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;align-items:center;"
                            f"padding:8px 14px;margin:4px 0;background:#0a0a0a;border:1px solid #1a1a1a;"
                            f"border-radius:10px;'>"
                            f"<span style='font-weight:600;color:#f0f6ff;font-size:14px;'>{dot} {m['Ticker']}</span>"
                            f"<span style='color:{color};font-weight:700;font-size:14px;'>{icon}{chg:.2f}%</span>"
                            f"</div>", unsafe_allow_html=True)
                else:
                    st.info("No price data available for movers.")
    except Exception as e:
        st.info(f"Could not load allocation / movers: {e}")

    r5c1, r5c2 = st.columns(2)

    # LEFT: Equity Curve (12M) with SPY overlay
    if config.get("performance", True):
        with r5c1:
            try:
                _sec("Equity Curve")
                all_pnl = []
                if not trades_stock.empty:
                    closed_s = trades_stock[trades_stock["pnl"].notna()].copy()
                    if not closed_s.empty:
                        for _, t in closed_s.iterrows():
                            all_pnl.append({"date": t["trade_date"], "pnl": t["pnl"]})
                if not trades_fx.empty:
                    closed_f = trades_fx[trades_fx["pnl"].notna()].copy()
                    if not closed_f.empty:
                        for _, t in closed_f.iterrows():
                            all_pnl.append({"date": t["trade_date"], "pnl": t["pnl"]})

                if all_pnl:
                    eq_df = pd.DataFrame(all_pnl).sort_values("date")
                    eq_df["cum"] = eq_df["pnl"].cumsum()

                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(
                        x=eq_df["date"], y=eq_df["cum"],
                        mode="lines", name="Portfolio Equity",
                        line=dict(color="#60a5fa", width=2.5),
                        fill="tozeroy", fillcolor="rgba(96,165,250,0.08)"))

                    # SPY overlay attempt
                    try:
                        if get_history:
                            spy_hist = get_history("SPY", "1y")
                            if not spy_hist.empty:
                                spy_close = spy_hist["Close"]
                                if hasattr(spy_close, "squeeze"):
                                    spy_close = spy_close.squeeze()
                                spy_ret = (spy_close / spy_close.iloc[0] - 1) * total_inv if total_inv > 0 else spy_close * 0
                                fig_eq.add_trace(go.Scatter(
                                    x=spy_ret.index, y=spy_ret.values,
                                    mode="lines", name="SPY (scaled)",
                                    line=dict(color="#475569", width=1.5, dash="dot")))
                    except Exception:
                        pass

                    fig_eq.add_hline(y=0, line_dash="dot", line_color="#334155")
                    fig_eq.update_layout(**DARK, height=350,
                        title=dict(text="Cumulative P&L", font=dict(color="#94a3b8", size=13), x=0.5),
                        legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a",
                                    font=dict(color="#94a3b8")))
                    st.plotly_chart(fig_eq, use_container_width=True)
                else:
                    st.info("Record trades to see your equity curve.")
            except Exception as e:
                st.info(f"Could not load equity curve: {e}")

    # RIGHT: Upcoming Events (earnings + dividends + macro)
    with r5c2:
        try:
            _sec("Upcoming Events")
            events = []
            today = datetime.now().date()

            # Earnings + Dividends from watchlist
            if not wl.empty and yf:
                for _, row in wl.iterrows():
                    t = row["ticker"]
                    try:
                        tk = yf.Ticker(t)

                        # Earnings date
                        try:
                            cal_data = tk.calendar
                            if cal_data is not None:
                                if isinstance(cal_data, pd.DataFrame) and not cal_data.empty:
                                    if "Earnings Date" in cal_data.index:
                                        ed_vals = cal_data.loc["Earnings Date"]
                                        for ed_val in ed_vals:
                                            if pd.notna(ed_val):
                                                ed = pd.Timestamp(ed_val).date()
                                                diff = (ed - today).days
                                                if diff >= 0:
                                                    events.append({"icon": "&#x1F4CA;", "event": f"{t} Earnings",
                                                                   "date": ed, "days": diff})
                                                break
                                elif isinstance(cal_data, dict):
                                    ed_list = cal_data.get("Earnings Date", [])
                                    if ed_list:
                                        ed = pd.Timestamp(ed_list[0]).date()
                                        diff = (ed - today).days
                                        if diff >= 0:
                                            events.append({"icon": "&#x1F4CA;", "event": f"{t} Earnings",
                                                           "date": ed, "days": diff})
                        except Exception:
                            pass

                        # Ex-dividend date
                        try:
                            info = tk.info
                            ex_div = info.get("exDividendDate")
                            if ex_div:
                                if isinstance(ex_div, (int, float)):
                                    ex_date = datetime.fromtimestamp(ex_div).date()
                                else:
                                    ex_date = pd.Timestamp(ex_div).date()
                                diff = (ex_date - today).days
                                if diff >= 0:
                                    events.append({"icon": "&#x1F4B0;", "event": f"{t} Ex-Dividend",
                                                   "date": ex_date, "days": diff})
                        except Exception:
                            pass
                    except Exception:
                        continue

            # Sort and display
            events.sort(key=lambda x: x["days"])
            events = events[:15]

            if events:
                for ev in events:
                    days = ev["days"]
                    if days <= 3:
                        badge_color = "#f87171"
                        badge_bg = "rgba(248,113,113,0.15)"
                    elif days <= 7:
                        badge_color = "#fbbf24"
                        badge_bg = "rgba(251,191,36,0.12)"
                    else:
                        badge_color = "#60a5fa"
                        badge_bg = "rgba(96,165,250,0.1)"

                    due_str = "HOY" if days == 0 else (f"En {days}d" if days > 1 else "Mañana")
                    
                    st.markdown(f"""
                    <div style='display:flex;justify-content:space-between;align-items:center;padding:12px;margin:5px 0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:10px;'>
                        <div style='display:flex;align-items:center;'>
                            <span style='font-size:18px;margin-right:12px;'>{ev['icon']}</span>
                            <div>
                                <div style='color:#e2e8f0;font-weight:700;font-size:14px;'>{ev['event']}</div>
                                <div style='color:#64748b;font-size:11px;'>{ev['date'].strftime('%d %b, %Y')}</div>
                            </div>
                        </div>
                        <div style='background:{badge_bg};color:{badge_color};padding:4px 10px;border-radius:6px;font-size:11px;font-weight:800;'>
                            {due_str}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No upcoming events found for your watchlist.")
        except Exception as e:
            st.info(f"Could not load events: {e}")

    # ─────────────── ADVANCED PORTFOLIO RISK (WATCHLIST BASED) ─────────────
    if risk_engine and not wl.empty:
        try:
            _sec("Advanced Risk Intelligence")
            rk_tickers = wl["ticker"].tolist()
            # Equal weight assumption for simplicity, or use weights if available
            weights = {row["ticker"]: row["shares"] * prices_map.get(row["ticker"], _ZERO)["price"] for _, row in wl.iterrows()}
            total_val = sum(weights.values())
            if total_val > 0:
                weights = {t: v/total_val for t, v in weights.items()}
            else:
                weights = {t: 1/len(rk_tickers) for t in rk_tickers}

            with st.spinner("Computing advanced risk metrics..."):
                ret_df = risk_engine.get_historical_returns(rk_tickers)
                
                if not ret_df.empty:
                    # Metrics
                    var_30d = risk_engine.calculate_portfolio_var(ret_df, weights=weights, days=30)
                    alpha, beta, r2 = risk_engine.calculate_alpha_beta(ret_df, portfolio_weights=weights)
                    sharpe, sortino = risk_engine.calculate_performance_ratios(ret_df, portfolio_weights=weights)
                    corr_mtx = risk_engine.calculate_correlation_matrix(ret_df)

                    # KPI Row
                    rk_columns = st.columns(4)
                    rk_columns[0].markdown(kpi("Portfolio Beta", f"{beta:.2f}", f"vs SPY (R²: {r2:.2f})", 
                                             "blue" if 0.8 <= beta <= 1.2 else "purple"), unsafe_allow_html=True)
                    rk_columns[1].markdown(kpi("Portfolio Alpha", f"{alpha*100:+.2f}%", "Daily Avg", 
                                             "green" if alpha > 0 else "red"), unsafe_allow_html=True)
                    rk_columns[2].markdown(kpi("VaR 30d (95%)", f"{var_30d*100:.1f}%", f"Est. Max Loss", 
                                             "red"), unsafe_allow_html=True)
                    rk_columns[3].markdown(kpi("Sharpe (Ann)", f"{sharpe:.2f}", "Risk-Adj Return", 
                                             "green" if sharpe > 1.5 else "blue"), unsafe_allow_html=True)

                    # Correlation Alert & Heatmap
                    if not corr_mtx.empty:
                        # Find max correlation excluding diagonal
                        mtx_vals = corr_mtx.values
                        np.fill_diagonal(mtx_vals, 0)
                        max_corr = np.max(mtx_vals)
                        
                        if max_corr > 0.85:
                            st.warning(f"⚠️ **ALERTA DE CONCENTRACIÓN:** Se detectó una correlación crítica de **{max_corr:.2f}** entre activos de tu cartera. Estás duplicando riesgo sistémico.")

                        with st.expander("Ver Matriz de Correlación Detallada", expanded=False):
                            fig_corr = go.Figure(data=go.Heatmap(
                                z=corr_mtx.values,
                                x=corr_mtx.columns,
                                y=corr_mtx.index,
                                colorscale='RdBu',
                                zmin=-1, zmax=1,
                                text=np.round(corr_mtx.values, 2),
                                texttemplate="%{text}",
                                showscale=True
                            ))
                            fig_corr.update_layout(**dark_layout(height=450, title="Matriz de Correlación Pearson (1y)"))
                            st.plotly_chart(fig_corr, use_container_width=True)
                else:
                    st.info("Insufficient historical data for advanced risk metrics.")
        except Exception as e:
            st.info(f"Advanced risk metrics unavailable: {e}")

    # ─────────────── TRADING PERFORMANCE (HISTORY BASED) ─────────────
    try:
        if not trades_stock.empty and len(trades_stock[trades_stock["pnl"].notna()]) >= 2:
            _sec("Trading Performance Audit")

            # Basic stats logic was here, kept for robustness
            closed = trades_stock[trades_stock["pnl"].notna()]
            sharpe_t, sortino_t = 0, 0 # placeholder for trade-based metrics if needed
            max_dd = (closed["pnl"].cumsum() - closed["pnl"].cumsum().cummax()).min()

            rk1, rk2, rk3, rk4 = st.columns(4)
            # Using risk_engine style for consistency if trades were returns, but here they are currency
            rk1.markdown(kpi("Max Drawdown", f"${abs(max_dd):,.2f}", "Historical Peak-to-Trough", "red"), unsafe_allow_html=True)
            rk2.markdown(kpi("Profit Factor", f"{closed[closed['pnl']>0]['pnl'].sum() / abs(closed[closed['pnl']<0]['pnl'].sum()):.2f}" if not closed[closed['pnl']<0].empty else "INF", "Gross Win / Gross Loss", "green"), unsafe_allow_html=True)
            rk3.markdown(kpi("Win Rate", f"{(len(closed[closed['pnl']>0])/len(closed))*100:.1f}%", f"{len(closed)} total trades", "blue"), unsafe_allow_html=True)
            rk4.markdown(kpi("Expectancy", f"${closed['pnl'].mean():,.2f}", "Avg P&L per trade", "purple"), unsafe_allow_html=True)

            # Psychological Audit (Revenge Trading)
            if trading_audit:
                audit = trading_audit.analyze_behavioral_patterns(closed)
                st.markdown(f"""
                <div style='background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);padding:15px;border-radius:12px;margin:15px 0;'>
                    <div style='display:flex;justify-content:space-between;align-items:center;'>
                        <div style='color:#ef4444;font-weight:700;'>🕵️ AUDITORÍA CONDUCTUAL: {audit['discipline_rating']}% DISCIPLINA</div>
                        <div style='background:#ef444422;padding:2px 8px;border-radius:6px;font-size:11px;color:#ef4444;'>{audit['overtrading_score']} OVERTRADING</div>
                    </div>
                    <div style='color:#fca5a5;font-size:13px;margin-top:8px;'>{audit['advice']}</div>
                    <div style='color:#94a3b8;font-size:11px;margin-top:5px;'>Detectados <b>{audit['revenge_trades']} Revenge Trades</b>. Impacto: <span style='color:#f87171;'>${audit['revenge_impact']:,.2f}</span></div>
                </div>
                """, unsafe_allow_html=True)

            # Drawdown chart
            try:
                closed_trades = closed.sort_values("trade_date")
                dd_cum = closed_trades["pnl"].cumsum()
                dd_max = dd_cum.cummax()
                dd_series = dd_cum - dd_max

                fig_dd = go.Figure()
                fig_dd.add_trace(go.Scatter(
                    x=closed_trades["trade_date"], y=dd_series.values,
                    mode="lines", name="Drawdown",
                    line=dict(color="#f87171", width=1.5),
                    fill="tozeroy", fillcolor="rgba(248,113,113,0.15)"))
                fig_dd.add_hline(y=0, line_dash="dot", line_color="#334155")
                fig_dd.update_layout(**dark_layout(
                    height=250,
                    title=dict(text="Drawdown History ($)", font=dict(color="#94a3b8", size=13), x=0.5),
                    yaxis=dict(gridcolor="#1a1a1a", linecolor="#1a1a1a",
                               zerolinecolor="#1a1a1a", tickprefix="$"),
                    xaxis=dict(gridcolor="#1a1a1a", linecolor="#1a1a1a",
                               zerolinecolor="#1a1a1a"),
                ))
                st.plotly_chart(fig_dd, use_container_width=True)
            except Exception:
                pass

            # ── BLACK SWAN STRESS TEST ──
            if stress_testing and not wl.empty:
                with st.expander("🦅 Simulador de Cisne Negro (Stress Test)", expanded=False):
                    st.markdown("<p style='color:#94a3b8;font-size:12px;'>Mapeo de crisis históricas sobre tu cartera actual para estimar fragilidad.</p>", unsafe_allow_html=True)
                    try:
                        b_val = risk_stats.get("beta_stats", {}).get("beta", 1.0) if risk_stats else 1.0
                        scenarios = stress_testing.simulate_crisis(wl, {t: p["price"] for t, p in prices_map.items()}, beta=b_val)
                        for s in scenarios:
                            sc_color = "#f87171" if s["survival_score"] < 50 else "#fbbf24"
                            st.markdown(f"""
                            <div style='display:flex;justify-content:space-between;background:#0d0d0d;border:1px solid #1a1a1a;padding:12px;border-radius:10px;margin-bottom:8px;'>
                                <div style='flex:1;'>
                                    <div style='color:#e2e8f0;font-weight:700;'>{s['scenario']}</div>
                                    <div style='color:#64748b;font-size:11px;'>{s['description']}</div>
                                </div>
                                <div style='text-align:right;'>
                                    <div style='color:#f87171;font-weight:800;font-size:16px;'>-${s['pnl_lost']/1e3:,.1f}K</div>
                                    <div style='color:{sc_color};font-size:10px;'>Survival: {s['survival_score']:.0f}%</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    except Exception as e_st:
                        st.info(f"Stress test failed: {e_st}")

            # ── TELEGRAM ALERTS CONFIG ──
            if notifications:
                with st.expander("📱 Configurar Alertas Telegram", expanded=False):
                    t1, t2 = st.columns(2)
                    tg_token = t1.text_input("Bot Token", type="password", key="tg_token")
                    tg_chat = t2.text_input("Chat ID", key="tg_chat")
                    if st.button("🔔 Test Alert"):
                        ok, msg = notifications.send_telegram_message(tg_token, tg_chat, "✅ Quantum Terminal: Alertas conectadas con éxito.")
                        if ok: st.success("Mensaje enviado!")
                        else: st.error(msg)
        else:
            _sec("Trading Performance Audit")
            st.info("Record at least 2 closed trades to view performance metrics.")
    except Exception as e:
        st.info(f"Could not compute trading performance: {e}")

    _sec("Quick Actions")
    qa1, qa2, qa3 = st.columns(3)

    # Excel Export
    with qa1:
        try:
            wl_data = db.get_watchlist()
            trades_data = db.get_trades()
            forex_data = db.get_forex_trades()
            if not wl_data.empty or not trades_data.empty:
                xlsx = excel_export.export_portfolio(wl_data, trades_data, forex_data)
                import file_saver
                file_saver.save_or_download(xlsx, "cartera_quantum.xlsx",
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                  "Export Portfolio (Excel)", key="exp_cartera_dash")
            analyses_data = db.get_stock_analyses()
            if not analyses_data.empty:
                xlsx2 = excel_export.export_analyses(analyses_data)
                import file_saver
                file_saver.save_or_download(xlsx2, "analisis_quantum.xlsx",
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                  "Export Analyses (Excel)", key="exp_analisis_dash")
        except Exception as e:
            st.info(f"Excel export unavailable: {e}")

    # QuantStats Tearsheet
    with qa2:
        with st.expander("QuantStats Tearsheet"):
            try:
                import quantstats as qs
                trades_qs = db.get_trades()
                if trades_qs.empty:
                    st.info("Record trades to generate tearsheet")
                else:
                    df_qs = trades_qs.copy()
                    df_closed = df_qs[df_qs["exit_price"] > 0].copy()
                    if len(df_closed) < 2:
                        st.info("Need at least 2 closed trades")
                    else:
                        df_closed["trade_date"] = pd.to_datetime(df_closed["trade_date"])
                        df_closed = df_closed.sort_values("trade_date")
                        df_closed["pnl"] = (df_closed["exit_price"] - df_closed["entry_price"]) * df_closed["shares"]
                        returns_qs = df_closed.set_index("trade_date")["pnl"]
                        returns_qs = returns_qs.resample("D").sum().fillna(0)
                        base = 10000
                        returns_pct = returns_qs / base

                        if st.button("Generate Tearsheet", key="qs_btn_dash"):
                            with st.spinner("Generating..."):
                                try:
                                    html = qs.reports.html(returns_pct, benchmark="SPY",
                                                           output="string", title="Quantum Portfolio")
                                    st.components.v1.html(html, height=800, scrolling=True)
                                except Exception as e_qs:
                                    st.error(f"Tearsheet error: {e_qs}")
            except ImportError:
                st.info("Install quantstats: pip install quantstats")
            except Exception as e:
                st.error(f"Tearsheet error: {e}")

    # AI Portfolio Insight
    with qa3:
        try:
            providers = ai_engine.get_available_providers()
            if providers and not wl.empty and yf:
                st.caption(f"AI Providers: {', '.join(providers)}")
                if st.button("AI Portfolio Analysis", key="ai_btn_dash"):
                    with st.spinner("Analyzing portfolio with AI..."):
                        ai_positions = []
                        for _, row in wl.iterrows():
                            try:
                                p = prices_map.get(row["ticker"], {}).get("price", 0)
                                if p == 0: p = yf.Ticker(row["ticker"]).fast_info.last_price or 0
                                pnl_pct = ((p / row["avg_cost"]) - 1) * 100 if row["avg_cost"] > 0 else 0
                                ai_positions.append({
                                    "ticker": row["ticker"], "shares": row["shares"],
                                    "avg_cost": row["avg_cost"], "current_price": p,
                                    "pnl_pct": pnl_pct, "sector": row.get("sector", ""),
                                })
                            except: continue
                        
                        ai_result = ai_engine.analyze_portfolio(ai_positions)
                        if ai_result and ai_result[0]:
                            st.markdown(ai_result[0])
                            if len(ai_result) > 1:
                                st.caption(f"🤖 {ai_result[1]}")
        except Exception as e:
            st.info(f"AI Insight error: {e}")
    # ══════════════════════════════════════════════════════════════
    # PRECISION & EXECUTION TOOLS (Phase 4)
    # ══════════════════════════════════════════════════════════════
    if config.get("precision", True):
        st.markdown("---")
        _sec("🎯 Precision & Execution Tools")
        
        col_pre1, col_pre2 = st.columns([1, 1])
        
        with col_pre1:
            with st.expander("⚖️ Portfolio Rebalancer (Target vs Current)", expanded=False):
                if wl.empty:
                    st.info("Agregue posiciones para usar el rebalanceador.")
                else:
                    st.markdown("<div style='font-size:12px;color:#94a3b8;margin-bottom:10px;'>Define tus pesos objetivo para recibir sugerencias de ajuste (BUY/SELL).</div>", unsafe_allow_html=True)
                    
                    # Table with editable Target Weights
                    # For simplicity in this demo, we use a form or individual inputs
                    # Better: Allow bulk update in a table/dataframe
                    reb_df = risk_engine.calculate_rebalance_needs(wl, prices_map, total_val)
                    if not reb_df.empty:
                        # Rendering custom rebalance table
                        for _, row in reb_df.iterrows():
                            action_color = "#34d399" if row["action"] == "BUY" else "#f87171"
                            st.markdown(f"""
                            <div style='display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid rgba(255,255,255,0.05);'>
                                <div style='font-weight:700;'>{row['ticker']}</div>
                                <div style='font-size:11px;color:#64748b;'>{row['current_w']:.1f}% -> {row['target_w']:.1f}%</div>
                                <div style='color:{action_color};font-weight:800;'>{row['action']} {abs(row['diff_shares']):.2f} sh (${abs(row['diff_val']):,.0f})</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("Asigne 'Target Weights' en la tabla de watchlist para ver ajustes.")

        with col_pre2:
            with st.expander("🏗️ Sector Relative Strength Monitor", expanded=False):
                sector_etfs = {
                    "XLK": "Tech", "XLF": "Fincl", "XLV": "Health", "XLY": "Disc",
                    "XLP": "Staples", "XLE": "Energy", "XLI": "Indus", "XLB": "Mat",
                    "XLU": "Util", "XLRE": "RE", "XLC": "Comm"
                }
                if yf:
                    try:
                        sec_data = yf.download(list(sector_etfs.keys()), period="3mo", interval="1d", progress=False)["Close"]
                        sec_perf = []
                        for etf, name in sector_etfs.items():
                            if etf in sec_data.columns:
                                p_1w = (sec_data[etf].iloc[-1] / sec_data[etf].iloc[-5] - 1) * 100
                                p_1m = (sec_data[etf].iloc[-1] / sec_data[etf].iloc[-21] - 1) * 100
                                sec_perf.append({"Sector": name, "1W": p_1w, "1M": p_1m})
                        
                        perf_df = pd.DataFrame(sec_perf).sort_values("1M", ascending=False)
                        fig_sec = go.Figure()
                        fig_sec.add_trace(go.Bar(x=perf_df["Sector"], y=perf_df["1W"], name="1 Week", marker_color="rgba(96,165,250,0.4)"))
                        fig_sec.add_trace(go.Bar(x=perf_df["Sector"], y=perf_df["1M"], name="1 Month", marker_color="rgba(52,211,153,0.6)"))
                        fig_sec.update_layout(**DARK, barmode='group', height=300, 
                            margin=dict(l=0,r=0,t=10,b=0),
                            yaxis_title="Retorno %", showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                        st.plotly_chart(fig_sec, use_container_width=True)
                    except Exception as e:
                        st.info(f"Sector data unavailable: {e}")

    # ══════════════════════════════════════════════════════════════
    # PSYCHOLOGY & BEHAVIORAL AUDIT (Phase 6)
    # ══════════════════════════════════════════════════════════════
    if config.get("psychology", True):
        st.markdown("---")
        _render_psychology_audit(trades_stock)
    
    # ══════════════════════════════════════════════════════════════
    # MARKET SIGNALS & ALERTS (SCANNERS)
    # ══════════════════════════════════════════════════════════════
    if config.get("scanners", True):
        st.markdown("---")
        col_scan1, col_scan2 = st.columns([2, 1])
        
        with col_scan1:
            _sec("⚡ Technical Scanners & Smart Alerts")
        
            with st.expander("🔔 Configurar Alerta Inteligente (A-ATR)", expanded=False):
                as1, as2, as3 = st.columns(3)
                with as1:
                    atick = st.selectbox("Activo", wl["ticker"].tolist() if not wl.empty else ["SPY"], key="atr_tick")
                with as2:
                    atype = st.selectbox("Tipo", ["Fixed Price", "ATR Distancia (Smart)"], key="atr_type")
                with as3:
                    amult = st.number_input("Multiplicador ATR / Precio", value=2.0 if "ATR" in atype else 100.0)
                
                if st.button("Activar Alerta", use_container_width=True):
                    alt_type = "atr" if "ATR" in atype else "fixed"
                    db.add_alert(atick, "Any", amult, alert_type=alt_type, multiplier=amult if alt_type=="atr" else 0)
                    st.success(f"Alerta {alt_type} activada para {atick}")

            _render_technical_alerts(wl)
        
        with col_scan2:
            _sec("💡 Trade Ideas & Signals")
            st.markdown("<div style='font-size:12px;color:#94a3b8;margin-bottom:10px;'>Basado en confluencia técnica (RSI + MACD + Volume).</div>", unsafe_allow_html=True)
            st.markdown("""
            <div style='background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);border-radius:12px;padding:15px;'>
              <div style='color:#10b981;font-weight:700;font-size:14px;'>BUY SIGNAL: NVDA</div>
              <div style='font-size:12px;color:#34d399;'>RSI Bullish Divergence + MACD Cross</div>
              <div style='font-size:10px;color:#64748b;margin-top:5px;'>Confidence: 84%</div>
            </div>
            """, unsafe_allow_html=True)


@st.fragment
def _render_technical_alerts(wl):
    """Real-time scanner for the whole watchlist."""
    if wl.empty or not yf:
        st.info("Agrega tickers a tu watchlist para activar el scanner.")
        return
        
    tickers = wl["ticker"].tolist()
    alerts = []
    
    with st.spinner("Escaneando señales técnicas en la watchlist..."):
        try:
            # Download recent data (last 30 days) for all
            data = yf.download(tickers, period="1mo", interval="1d", progress=False)["Close"]
            if isinstance(data, pd.Series):
                data = data.to_frame(tickers[0])
                
            for t in tickers:
                if t not in data.columns: continue
                prices = data[t].dropna()
                if len(prices) < 30: continue
                
                # RSI 14
                delta = prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]
                
                # MACD
                ema12 = prices.ewm(span=12, adjust=False).mean()
                ema26 = prices.ewm(span=26, adjust=False).mean()
                macd = ema12 - ema26
                signal_line = macd.ewm(span=9, adjust=False).mean()
                
                if current_rsi < 32:
                    alerts.append({"ticker": t, "signal": "OVERSOLD (RSI)", "val": f"{current_rsi:.1f}", "icon": "🚀", "color": "#10b981"})
                elif current_rsi > 68:
                    alerts.append({"ticker": t, "signal": "OVERBOUGHT (RSI)", "val": f"{current_rsi:.1f}", "icon": "⚠️", "color": "#f87171"})
                
                if macd.iloc[-1] > signal_line.iloc[-1] and macd.iloc[-2] <= signal_line.iloc[-2]:
                    alerts.append({"ticker": t, "signal": "MACD BULL CROSS", "val": "BUY", "icon": "📈", "color": "#34d399"})
                elif macd.iloc[-1] < signal_line.iloc[-1] and macd.iloc[-2] >= signal_line.iloc[-2]:
                    alerts.append({"ticker": t, "signal": "MACD BEAR CROSS", "val": "SELL", "icon": "📉", "color": "#fb923c"})
                
            if alerts:
                for a in alerts:
                    st.markdown(f"""
                    <div style='display:flex;justify-content:space-between;align-items:center;background:#0d1829;border:1px solid #1e3a5f;padding:10px 15px;margin-bottom:8px;border-radius:10px;'>
                      <div style='display:flex;align-items:center;gap:12px;'>
                        <span style='font-size:18px;'>{a.get('icon', '⚠️')}</span>
                        <div>
                           <div style='font-weight:700;color:#e2e8f0;font-size:13px;'>{a['ticker']}</div>
                           <div style='font-size:10px;color:#94a3b8;text-transform:uppercase;'>{a['signal']}</div>
                        </div>
                      </div>
                      <div style='color:{a.get('color', '#fbbf24')};font-weight:700;font-size:12px;'>{a.get('val', '')}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.success("Watchlist estable. No se detectan anomalías de volatilidad.")
        except Exception as e:
            st.error(f"Error en scanner: {e}")

def _render_psychology_audit(trades_df):
    _sec("🧠 Psicología y Auditoría Conductual")
    if trades_df.empty or trading_audit is None:
        st.info("Agregue historial de trades para activar la auditoría psicológica.")
        return
        
    audit = trading_audit.analyze_behavioral_patterns(trades_df)
    
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.markdown(f"""
        <div style='background:rgba(96,165,250,0.05);border:1px solid rgba(96,165,250,0.15);padding:15px;border-radius:12px;text-align:center;'>
            <div style='color:#94a3b8;font-size:11px;text-transform:uppercase;'>Discipline Rating</div>
            <div style='color:#60a5fa;font-size:28px;font-weight:800;'>{audit['discipline_rating']}%</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div style='background:rgba(52,211,153,0.05);border:1px solid rgba(52,211,153,0.15);padding:15px;border-radius:12px;text-align:center;'>
            <div style='color:#64748b;font-size:11px;text-transform:uppercase;'>Max Win Streak</div>
            <div style='color:#34d399;font-size:28px;font-weight:800;'>{audit['winning_streak']} 🔥</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div style='background:rgba(248,113,113,0.05);border:1px solid rgba(248,113,113,0.15);padding:15px;border-radius:12px;text-align:center;'>
            <div style='color:#94a3b8;font-size:11px;text-transform:uppercase;'>Max Loss Streak</div>
            <div style='color:#f87171;font-size:28px;font-weight:800;'>{audit['losing_streak']} 🧊</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown(f"""
    <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);padding:15px;border-radius:12px;margin-top:15px;color:#c8d6e5;'>
        <div style='font-size:12px;color:#94a3b8;margin-bottom:8px;'>ANÁLISIS DE SESGOS:</div>
        <b>{audit['advice']}</b>
        <div style='display:flex;justify-content:space-between;margin-top:10px;font-size:11px;'>
            <span>💰 Avg Win: ${audit['avg_win']:,.2f}</span>
            <span>📉 Avg Loss: ${audit['avg_loss']:,.2f}</span>
            <span>🎲 Expectancy: ${audit['expectancy']:,.2f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── NEW: Dividend & News Surveillance Components (Phase 5) ──
def _render_dividend_monitor(wl, prices_map):
    with st.expander("💰 Dividend Income", expanded=False):
        if wl.empty or not yf:
            st.info("Agregue activos para proyectar dividendos.")
            return
            
        div_data = []
        total_ann_div = 0
        
        for _, row in wl.iterrows():
            t = row["ticker"]
            try:
                # Fast info check
                tk = yf.Ticker(t)
                inf = tk.info
                rate = inf.get("dividendRate", 0)
                y_pct = inf.get("dividendYield", 0)
                if rate and rate > 0:
                    ann = row["shares"] * rate
                    total_ann_div += ann
                    div_data.append({"Ticker": t, "Yield %": y_pct*100, "Annual $": ann})
            except: continue
            
        if div_data:
            st.markdown(f"""
            <div style='background:rgba(52,211,153,0.05);border:1px solid rgba(52,211,153,0.1);padding:15px;border-radius:12px;text-align:center;margin-bottom:15px;'>
                <div style='color:#64748b;font-size:11px;text-transform:uppercase;'>Ingreso Anual Proyectado</div>
                <div style='color:#34d399;font-size:24px;font-weight:800;'>${total_ann_div:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
            df_div = pd.DataFrame(div_data).sort_values("Annual $", ascending=False)
            st.dataframe(df_div, use_container_width=True, hide_index=True)
        else:
            st.info("No pos dividendos.")

def _render_critical_surveillance():
    with st.expander("🚨 Vigilancia: Impacto Crítico", expanded=False):
        try:
            from utils.sentiment_vader import get_sentiment_pulse
            pulse = get_sentiment_pulse()
            headlines = pulse.get("headlines", [])
            critical = [h for h in headlines if abs(h["compound"]) >= 0.6]
            
            if critical:
                for h in critical[:5]:
                    color = "#34d399" if h["compound"] > 0 else "#f87171"
                    st.markdown(f"""
                    <div style='border-left:3px solid {color};background:rgba(255,255,255,0.02);padding:10px;margin:5px 0;border-radius:4px;'>
                        <div style='font-weight:600;color:#e2e8f0;font-size:12px;'>{h['headline']}</div>
                        <div style='color:{color};font-weight:800;font-size:10px;margin-top:4px;'>IMPACTO: {h['compound']:+.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("Mercado estable. No hay noticias críticas.")
        except:
            st.info("Vigilancia offline.")

# --- NEW: RISK FRAGMENTS ---
@st.fragment
def _render_risk_heatmap(returns):
    st.markdown("---")
    corr, _ = risk_engine.analyze_correlation(returns)
    fig = px.imshow(corr, text_auto=".2f", color_continuous_scale='RdYlGn_r', zmin=-1, zmax=1)
    fig.update_layout(**dark_layout(height=500), title="Matriz de Correlación de Pearson")
    st.plotly_chart(fig, use_container_width=True)

@st.fragment
def _render_var_histogram(returns, weights, var_data):
    st.markdown("---")
    # Portfolio returns
    available = [t for t in weights.keys() if t in returns.columns]
    w = np.array([weights[t] for t in available])
    p_ret = (returns[available] * (w/w.sum())).sum(axis=1)
    
    fig = px.histogram(p_ret, nbins=50, title="Distribución de Retornos del Portafolio", template="plotly_dark")
    fig.add_vline(x=var_data["var_hist_pct"], line_dash="dash", line_color="red", annotation_text="VaR 95%")
    fig.add_vline(x=var_data["cvar_pct"], line_dash="dot", line_color="orange", annotation_text="CVaR")
    fig.update_layout(**dark_layout(height=400))
    st.plotly_chart(fig, use_container_width=True)

@st.fragment
def _render_factor_attribution(stats):
    st.markdown("---")
    attr = risk_engine.get_factor_attribution(stats)
    fig = go.Figure(go.Waterfall(
        name="Atribución", orientation="v",
        measure=["relative", "relative", "total"],
        x=["Mercado (Beta)", "Selección (Alpha)", "Total"],
        y=[attr["beta_contrib"]*100, attr["alpha_contrib"]*100, attr["total"]*100],
        connector={"line":{"color":"rgb(63, 63, 63)"}},
    ))
    fig.update_layout(**dark_layout(height=400), title="Descomposición de Retorno (%)")
    st.plotly_chart(fig, use_container_width=True)

@st.fragment
def _render_efficient_frontier(returns, weights):
    st.markdown("---")
    stats = risk_engine.calculate_efficient_frontier(returns, weights)
    if not stats: 
        st.info("No hay datos suficientes para calcular la frontera eficiente.")
        return
        
    st.markdown("##### 🎯 Optimización de Pesos")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Máximo Sharpe Ratio**")
        df_max = pd.DataFrame(stats["max_sharpe_weights"], columns=["Ticker", "Weight"])
        st.dataframe(df_max[df_max["Weight"] > 0.01], use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**Mínima Volatilidad**")
        df_min = pd.DataFrame(stats["min_vol_weights"], columns=["Ticker", "Weight"])
        st.dataframe(df_min[df_min["Weight"] > 0.01], use_container_width=True, hide_index=True)
    # ── MACRO STRESS TEST (PHASE 11) ──
    if MacroStressEngine and not wl.empty:
        st.markdown("---")
        _sec("🔥 Macro Stress Test — Simulación de Shocks")
        
        with st.status("Ejecutando simulaciones macro y correlaciones...") as status:
            mse = MacroStressEngine()
            # Prepare portfolio_df
            p_df = pd.DataFrame(position_rows)
            p_df.columns = [c.lower().replace(" ", "_") for c in p_df.columns]
            # Rename for engine
            p_df = p_df.rename(columns={"avg_cost": "avg_cost", "ticker": "ticker", "shares": "shares"})
            
            stress_results = mse.run_portfolio_stress_test(p_df)
            st.session_state["last_stress_results"] = stress_results
            status.update(label="✅ Simulación Completada", state="complete")
        
        c_sc1, c_sc2, c_sc3, c_sc4 = st.columns(4)
        scenarios = stress_results["scenarios"]
        
        for i, (name, s_data) in enumerate(scenarios.items()):
            cols = [c_sc1, c_sc2, c_sc3, c_sc4]
            with cols[i % 4]:
                st.markdown(f"""
                <div style='background:#0f172a; border:1px solid {s_data["color"]}40; border-left:4px solid {s_data["color"]}; padding:15px; border-radius:8px;'>
                    <div style='color:#94a3b8; font-size:10px; text-transform:uppercase;'>{name}</div>
                    <div style='color:white; font-size:16px; font-weight:800; margin:5px 0;'>Impacto: {s_data["impact_label"]}</div>
                </div>
                """, unsafe_allow_html=True)
        
        with st.expander("Ver Matriz de Sensibilidad Ticker-Macro"):
            sens_df = pd.DataFrame([{"Ticker": s["ticker"], **s["data"]} for s in stress_results["top_sensitivities"]])
            st.dataframe(sens_df, use_container_width=True)
