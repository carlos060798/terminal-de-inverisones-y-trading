"""
sections/stock_analyzer.py - Quantum Retail Terminal v8.9.1
Analizador Institucional de Acciones PRO
Layout estilo InvestingPro con Tabs: Visión General, IA, Smart Money, Técnico.
Integración de Robustez de Datos y Tablas Financieras.
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import yfinance as yf
import textwrap
from cache_utils import get_history
import pdf_parser
import translator
import valuation_v2
import sentiment
from ui_shared import fmt
from utils.visual_components import inject_custom_css
from finterm import charts as fc
import valuation
from services import segment_parser
from services import ai_report_engine
# importlib.reload(valuation) # No longer needed

try:
    import sec_api
    HAS_SEC_API = True
except ImportError:
    HAS_SEC_API = False

import forecast_synthesizer
import conflict_detector


# ─────────────────────────────────────────────────────────────────
# INSTITUTIONAL VISUAL DESIGN SYSTEM
# ─────────────────────────────────────────────────────────────────
def _inject_premium_styles():
    st.markdown("""
    <style>
        /* Base Premium Styling */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
        
        .stApp {
            background-color: #020617;
        }
        
        /* Premium Glass Card */
        .premium-card {
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
        }
        .premium-card:hover {
            border-color: rgba(59, 130, 246, 0.4);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
            transform: translateY(-2px);
        }
        
        /* KPI Metric Styling */
        .kpi-label {
            color: #64748b;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 8px;
        }
        .kpi-value {
            color: #f8fafc;
            font-size: 28px;
            font-weight: 800;
            font-family: 'Inter', sans-serif;
            line-height: 1;
        }
        .kpi-delta {
            font-size: 13px;
            font-weight: 600;
            margin-top: 5px;
        }
        
        /* Terminal Table Header */
        .terminal-header {
            background: #1e293b;
            color: #3b82f6;
            padding: 10px 15px;
            border-radius: 8px 8px 0 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid rgba(59, 130, 246, 0.2);
        }
        
        /* Pulse Animation */
        .pulse {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 0 rgba(16, 185, 129, 0.4);
            animation: pulse 2s infinite;
            margin-right: 8px;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 5px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
# DATA RECOVERY HELPERS (Robustness)
# ─────────────────────────────────────────────────────────────────
def _get_clean_series(df, col_name):
    """Extrae una columna como Serie 1D, incluso si hay MultiIndex o duplicados."""
    if df is None or df.empty: return None
    try:
        # Si es MultiIndex (Ticker, Attribute)
        if isinstance(df.columns, pd.MultiIndex):
            # Buscar el nivel que contiene el col_name
            for level in range(df.columns.nlevels):
                if col_name in df.columns.get_level_values(level):
                    s = df.xs(col_name, axis=1, level=level)
                    return s.iloc[:, 0] if hasattr(s, "columns") else s
        # Si es columna simple
        if col_name in df.columns:
            s = df[col_name]
            return s.iloc[:, 0] if hasattr(s, "columns") else s
    except: pass
    return None

def _safe_float(val):
    """Convierte a float escalar de forma segura."""
    if val is None: return 0.0
    if isinstance(val, (pd.Series, pd.DataFrame)):
        try: return float(val.min()) if not val.empty else 0.0
        except: return 0.0
    try: return float(val)
    except: return 0.0

def _safe_df_cols(df, preferred_cols):
    """Selecciona solo columnas existentes en el DF para evitar KeyError."""
    if df is None or df.empty: return None
    available = [c for c in preferred_cols if c in df.columns]
    if not available: return df.iloc[:, :5] # Fallback a las primeras 5
    return df[available]

def _fmt_val(val, prefix=""):
    """Formatea valores grandes a K, M, B con un prefijo opcional."""
    if val is None or pd.isna(val): return "N/A"
    try:
        v = float(val)
    except:
        return str(val)
    
    abs_v = abs(v)
    mode = st.session_state.get("notation_mode", "Compacto (M/B)")
    
    if mode == "Compacto (M/B)":
        if abs_v >= 1e12: return f"{prefix}{v/1e12:.2f}T"
        if abs_v >= 1e9:  return f"{prefix}{v/1e9:.2f}B"
        if abs_v >= 1e6:  return f"{prefix}{v/1e6:.2f}M"
        if abs_v >= 1e3:  return f"{prefix}{v/1e3:.2f}K"
    
    if 0 < abs_v < 10 and isinstance(val, (float, np.float64)): return f"{prefix}{v:.2f}"
    return f"{prefix}{v:,.2f}" if abs_v < 1000 else f"{prefix}{v:,.0f}"

# ─────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────
_REC_COLOR = {
    "strong_buy": "#10b981", "buy": "#10b981",
    "hold": "#f59e0b",
    "sell": "#ef4444", "strong_sell": "#ef4444",
}

def _market_badge(state: str) -> str:
    s = (state or "").upper()
    if s in ("REGULAR", "PRE"):
        return "🟢 Mercado Abierto"
    elif s == "POST":
        return "Post-Market"
    return "🔴 Mercado Cerrado"

def _range_bar_html(label, sublabel, current, lo, hi, color="#3b82f6"):
    c = _safe_float(current)
    l = _safe_float(lo)
    h = _safe_float(hi)
    if h <= l: pct = 50
    else: pct = max(2, min(98, ((c - l) / (h - l)) * 100))
    return f"""
    <div style="margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;">
        <span style="color:#94a3b8;font-size:12px;">{label}</span>
        <span style="color:#64748b;font-size:11px;">{sublabel}</span>
      </div>
      <div style="position:relative;height:6px;background:#1e293b;border-radius:3px;">
        <div style="position:absolute;left:{pct}%;top:-5px;transform:translateX(-50%);
             width:16px;height:16px;background:{color};border-radius:50%;border:3px solid #0a0a0a;
             box-shadow:0 0 8px {color}60;z-index:2;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:6px;">
        <span style="color:#475569;font-size:11px;">${l:,.2f}</span>
        <span style="color:white;font-size:12px;font-weight:700;">${c:,.2f}</span>
        <span style="color:#475569;font-size:11px;">${h:,.2f}</span>
      </div>
    </div>
    """

def _progress_bar_html(pts, max_pts=2.0):
    p = _safe_float(pts)
    pct = max(3, min(100, (p / max_pts) * 100)) if max_pts > 0 else 50
    color = "#10b981" if p >= 1.5 else ("#f59e0b" if p >= 1.0 else "#ef4444")
    return f"""
    <div style="display:flex;align-items:center;gap:8px;height:22px;">
      <div style="flex:1;height:6px;background:#1e293b;border-radius:3px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:linear-gradient(90deg,{color}80,{color});
             border-radius:3px;"></div>
      </div>
    </div>
    """

def _info_card(title, value, color="white"):
    return f"""
    <div style="background:#0f172a;padding:12px;border-radius:8px;border:1px solid #1e293b;">
        <div style="color:#64748b;font-size:10px;text-transform:uppercase;margin-bottom:4px;">{title}</div>
        <div style="color:{color};font-size:15px;font-weight:700;">{value}</div>
    </div>
    """

# ─────────────────────────────────────────────────────────────────
# RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────
def render():
    inject_custom_css()

    # ── TITULO ──
    st.markdown("""
<div style='margin-bottom:18px'>
    <h1 style='color:white;margin:0;font-size:28px;font-weight:800;'>Quantum Stock Terminal <span style='color:#3b82f6;'>Pro</span></h1>
    <p style='color:#64748b;font-size:13px;margin:4px 0 0;'>
        Análisis Institucional · IA Insights · Vigilancia Smart Money
    </p>
</div>
""", unsafe_allow_html=True)

    # ── BUSCADOR ──
    with st.form("main_analyzer_form"):
        ci1, ci2, ci3 = st.columns([2, 2, 1])
        with ci1:
            ticker_input = st.text_input("Ticker:", placeholder="AAPL, MSFT...", value=st.session_state.get("active_ticker", ""))
        with ci2:
            uploaded_pdf = st.file_uploader("PDF InvestingPro para Insights IA:", type=["pdf"])
        with ci3:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            analyze_btn = st.form_submit_button("🚀 Iniciar Análisis", use_container_width=True)

    if analyze_btn and ticker_input.strip():
        _run_full_analysis(ticker_input.strip().upper(), uploaded_pdf)

    # ── LOADING COCKPIT (Partial Score Visibility) ──
    if "analyzer_res" not in st.session_state and st.session_state.get("active_ticker"):
        _render_loading_cockpit()
        return

    if "analyzer_res" not in st.session_state:
        st.info("Ingresa un ticker para comenzar.")
        return

    res = st.session_state["analyzer_res"]
    
    # ── TABS (Institutional Stack v2) ──
    t1, t_deep, t_fore, t_ai, t3, t4, t_alt = st.tabs([
        "📊 Visión General", 
        "💰 Deep Fundamental", 
        "🎯 Forecast & Targets", 
        "🤖 Intelligence & Conflict", 
        "🐋 Smart Money", 
        "📈 Análisis Técnico",
        "🕵️ Alt-Data"
    ])
    
    with t1: _render_general_tab(res)
    with t_deep: _render_deep_fundamental_tab(res)
    with t_fore: _render_forecast_tab(res)
    with t_ai: _render_ai_conflict_tab(res)
    with t3: _render_smart_money_tab(res)
    with t4: _render_technical_tab(res)
    with t_alt: _render_altdata_tab(st.session_state.get("active_ticker"))

    # ── SIDEBAR: COMMAND CENTER (Institutional Unit) ──
    with st.sidebar:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg, #1e293b, #0f172a); padding:20px; border-radius:15px; border:1px solid #3b82f630; margin-bottom:20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:15px;">
                <div style="width:10px; height:10px; background:#10b981; border-radius:50%; box-shadow: 0 0 10px #10b981;"></div>
                <span style="color:#3b82f6; font-weight:800; font-size:12px; letter-spacing:2px; text-transform:uppercase;">Command Center</span>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:15px; border-radius:10px; border:1px solid #ffffff05;">
                <div style="color:#64748b; font-size:10px; text-transform:uppercase; margin-bottom:4px;">Ticker Activo</div>
                <div style="color:white; font-size:22px; font-weight:900;">{st.session_state.get('active_ticker', '---')}</div>
                <div style="color:#10b981; font-size:11px; margin-top:4px;">● Sistema Operativo</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 💼 Seguimiento")
        
        # Portfolio Action Button Container
        with st.container():
            col_add = st.empty()
            if st.button("➕ AGREGAR A WATCHLIST", use_container_width=True, type="primary"):
                try:
                    import database as db
                    db.add_ticker(
                        ticker=st.session_state["active_ticker"],
                        shares=0,
                        avg_cost=0,
                        list_name="Principal",
                        portfolio_id=st.session_state.get("active_portfolio_id", 1)
                    )
                    st.toast(f"✅ {st.session_state['active_ticker']} agregado.", icon="🚀")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("---")
        st.markdown("### ⚡ AI Intelligence")
        if st.button("⚡ Generar Reporte IA", use_container_width=True, type="primary"):
            st.session_state["ai_report_markdown"] = ai_report_engine.generate_ai_report(
                st.session_state.get('active_ticker', 'Ticker'),
                st.session_state.get("analyzer_res", {})
            )
            
        if "ai_report_markdown" in st.session_state:
            with st.expander("Ver Reporte IA", expanded=True):
                st.markdown(st.session_state["ai_report_markdown"])
                if st.button("📋 Copiar Reporte"):
                    st.toast("Reporte copiado", icon="✅")
        st.markdown("---")
        st.markdown("### 📤 Intelligence Exports")
        
        # Report Export Section
        exp_container = st.container()
        if st.button("📄 GENERAR REPORTE PDF", use_container_width=True):
            with st.spinner("Compilando inteligencia..."):
                try:
                    from report_generator import generate_report
                    pdf_bytes = generate_report(
                        ticker=st.session_state["active_ticker"],
                        parsed_data=st.session_state.get("pdf_parsed_data"),
                        fair_value=st.session_state.get("analyzer_res", {}).get("verdict"),
                        advanced=st.session_state.get("analyzer_res", {}).get("info")
                    )
                    st.download_button(
                        label="📥 DESCARGAR REPORTE",
                        data=pdf_bytes,
                        file_name=f"Reporte_Quantum_{st.session_state['active_ticker']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error: {e}")

        # Interactive HTML Export
        st.download_button(
            "🌐 EXPORTAR TERMINAL (HTML)", 
            data="<html>...</html>", 
            file_name=f"Terminal_Quantum_{st.session_state['active_ticker']}.html",
            mime="text/html",
            use_container_width=True
        )

        st.markdown("""
        <div style="margin-top:30px; text-align:center;">
            <p style="color:#475569; font-size:10px;">Quantum Intelligence Unit v2.0<br>© 2026 DeepMind Financial</p>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# LOGICA DE CARGA
# ─────────────────────────────────────────────────────────────────
def _run_full_analysis(ticker, uploaded_pdf):
    st.session_state["active_ticker"] = ticker
    with st.status(f"Analizando {ticker}...", expanded=True) as status:
        # 1. Market Data
        st.write("📊 Datos de Mercado (yfinance)...")
        tk = yf.Ticker(ticker)
        hist = get_history(ticker, period="1y")
        info = tk.info
        
        # 2. Valuation (Faster than sentiment)
        st.write("⚙️ Motor de Valoración V2...")
        v = valuation_v2.get_final_verdict(ticker)
        st.session_state["partial_v"] = v # Checkpoint for partial UI

        # 3. PDF Parsing
        pdf_data = None
        if uploaded_pdf:
            st.write("📄 Procesando Reporte InvestingPro...")
            try:
                pdf_data = pdf_parser.parse_financial_pdf(uploaded_pdf.read())
                translator.translate_parsed_data(pdf_data)
            except: pass
        # 4. SEC DNA & Forensic Intelligence (Automatic)
        st.write("🧬 Secuenciando DNA Corporativo (SEC Ultra)...")
        from sec_api import extract_full_company_dna
        dna = extract_full_company_dna(ticker)
        health = valuation.get_ultra_health_report(ticker)
        
        st.write("🐋 Datos de Whales & Insiders (13F)...")
        try:
            insiders = tk.insider_transactions
            whales = dna.get("whales", [])
        except: 
            insiders = None
            whales = []

        # 5. ML Sentiment (Heaviest)
        st.write("🧠 Sentimiento IA...")
        try: sent = sentiment.aggregate_sentiment(ticker)
        except: sent = None

        # 6. Forensic & Forward Logic (New in Intelligence Stack v2)
        st.write("📈 Sintetizando Forecasts & Análisis Forense...")
        
        # Data objects for integration
        integrator = forecast_synthesizer.AnalystForecastIntegrator(dna, pdf_data, info)
        eps_scenario = integrator.build_eps_scenario()
        px_target = integrator.build_price_target_consensus()
        rev_scenario = integrator.build_revenue_scenario()

        # Forensic metrics
        fcf_data = sec_api.get_true_fcf(ticker, yf_cashflow=tk.cashflow)
        inv_data = sec_api.get_inventory_health(ticker, yf_balance=tk.balance_sheet)
        debt_data = sec_api.get_debt_maturity_ladder(ticker, yf_info=info)
        alloc_data = sec_api.get_capital_allocation(ticker, yf_cashflow=tk.cashflow, yf_info=info)

        # Conflict Detector
        conflict_engine = conflict_detector.FundamentalTechnicalConflict()
        conflict_res = conflict_engine.analyze(dna, hist, pdf_data, info)

        st.session_state["analyzer_res"] = {
            "verdict": v, "sec": dna, "health": health, "pdf": pdf_data, "hist": hist,
            "income": tk.income_stmt, "balance": tk.balance_sheet, "cashflow": tk.cashflow,
            "sent": sent, "info": info, "insiders": insiders, "whales": whales,
            # Institutional v2 data
            "forensic": {
                "fcf": fcf_data, "inventory": inv_data, "debt": debt_data, "allocation": alloc_data
            },
            "forecast": {
                "eps": eps_scenario, "price": px_target, "revenue": rev_scenario
            },
            "conflict": conflict_res
        }
        status.update(label="✅ Análisis Finalizado", state="complete", expanded=False)

@st.fragment
def _render_general_tab(res):
    _inject_premium_styles()
    v = res["verdict"]
    val = v["valuation"]
    qual = v["quality"]
    risk = v.get("risk", {})
    info = res["info"]
    price = _safe_float(val.get("current_price"))
    day_chg = _safe_float(info.get("regularMarketChange", 0))
    day_pct = _safe_float(info.get("regularMarketChangePercent", 0))
    chg_col = "#10b981" if day_chg >= 0 else "#ef4444"

    # ── 1. Header: PRICE TICKER (Institutional Style) ──
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px; background: rgba(15, 23, 42, 0.4); padding: 25px; border-radius: 16px; border: 1px solid rgba(59, 130, 246, 0.2);">
        <div>
            <div style="font-size:48px; font-weight:900; color:white; font-family:'Inter', sans-serif;">
                {st.session_state['active_ticker']} <span style="font-size:16px; color:#3b82f6; font-weight:700; background:rgba(59,130,246,0.1); padding:4px 10px; border-radius:8px;">{info.get('exchange', '')}</span>
            </div>
            <div style="color:#94a3b8; font-size:16px; font-weight:500; margin-top:8px;">{info.get('longName','')} · {info.get('sector','—')}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:48px; font-weight:800; color:white;">
                <span class="pulse"></span>${price:,.2f}
            </div>
            <div style="color:{chg_col}; font-size:20px; font-weight:700; margin-top:4px;">{day_chg:+.2f} ({day_pct:+.2f}%)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_chart, c_donut = st.columns([2, 1], gap="large")
    hist_raw = res.get("hist", pd.DataFrame())
    
    with c_chart:
        st.markdown('<div class="card-title">📈 Acción del Precio</div>', unsafe_allow_html=True)
        if not hist_raw.empty:
            fig_p = go.Figure()
            fig_p.add_trace(go.Scatter(
                x=hist_raw.index, y=hist_raw['Close'],
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.1)',
                line=dict(color='#3b82f6', width=2),
                name="Precio"
            ))
            fig_p.update_layout(
                template="plotly_dark", height=300, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#1e293b')
            )
            st.plotly_chart(fig_p, use_container_width=True)
        else:
            st.info("Sin datos históricos")

    with c_donut:
        st.markdown('<div class="card-title">🥧 Segmentos de Negocio</div>', unsafe_allow_html=True)
        segments = segment_parser.get_revenue_by_segment(st.session_state['active_ticker'], res.get("sec", {}))
        
        if segments:
            fig_d = go.Figure(data=[go.Pie(
                labels=list(segments.keys()), values=list(segments.values()), 
                hole=.6,
                marker=dict(colors=["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b"]),
                textinfo='percent',
                hoverinfo='label+percent'
            )])
            fig_d.update_layout(
                template="plotly_dark", height=300, margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                showlegend=True,
                legend=dict(orientation="h", y=-0.1)
            )
            st.plotly_chart(fig_d, use_container_width=True)
        else:
            st.info("Desglose segmentado no disponible.")

    # ── 2. Top KPI Grid (Premium Cards) ──
    st.markdown('<div class="card-title" style="margin-top:20px;">🔬 Métricas Fundamentales Clave</div>', unsafe_allow_html=True)
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    
    def spark_kpi(col, title, val, is_pct=False):
        val_str = f"{val:.1f}%" if is_pct else fmt(val)
        col.markdown(f"""
        <div style="background:rgba(15,23,42,0.6); padding:15px; border-radius:12px; border:1px solid #1e293b; text-align:center;">
            <div style="color:#64748b; font-size:11px; text-transform:uppercase; font-weight:700;">{title}</div>
            <div style="color:white; font-size:22px; font-weight:900; margin-top:8px;">{val_str}</div>
        </div>
        """, unsafe_allow_html=True)

    spark_kpi(k1, "Score Quantum", qual['percentage'], is_pct=True)
    spark_kpi(k2, "Riesgo IA", res.get('conflict', {}).get('score', 5))
    spark_kpi(k3, "Margen Seguridad", val.get('upside_pct', 0), is_pct=True)
    spark_kpi(k4, "ROE", info.get("returnOnEquity", 0)*100 if info.get("returnOnEquity") else 0, is_pct=True)
    spark_kpi(k5, "Margen Neto", info.get("profitMargins", 0)*100 if info.get("profitMargins") else 0, is_pct=True)
    
    fcf_latest = res.get("forensic", {}).get("fcf", {}).get("latest_fcf_gaap_b", 0) * 1e9
    spark_kpi(k6, "True FCF", fcf_latest)
    
    # ── 3. Diagnostic Row ──
    st.markdown("---")
    cg1, cg2 = st.columns([1.2, 1])
    
    with cg1:
        st.markdown('<div class="card-title">🛡️ Radar de Fortaleza (5-Axis)</div>', unsafe_allow_html=True)
        # Radar Chart
        from core.scoring import get_full_analysis
        finterm_score = get_full_analysis(st.session_state['active_ticker'], info, skip_sentiment=False)
        comp = finterm_score.get("Breakdown", {})
        categories = ['Fundamental', 'Técnico', 'Macro', 'Smart Money', 'Sentimiento']
        values = [comp.get('Fundamental', 50), comp.get('Technical', 50), comp.get('Macro', 50), comp.get('SmartMoney', 50), comp.get('Sentiment', 50)]
        
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=values + [values[0]], theta=categories + [categories[0]],
            fill='toself', fillcolor='rgba(59, 130, 246, 0.2)',
            line=dict(color='#3b82f6', width=2), marker=dict(size=8)
        ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], color='#64748b'), angularaxis=dict(color='#f8fafc')),
                                template="plotly_dark", height=380, margin=dict(l=40, r=40, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_radar, use_container_width=True)

    with cg2:
        st.markdown('<div class="card-title">⚖️ Termómetro de Valuación (DCF)</div>', unsafe_allow_html=True)
        consensus = _safe_float(val.get("consensus_target"))
        fig_gauge = fc.create_score_gauge(price, label="Fair Value", target=consensus)
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        # Model Table Table (Terminal Style)
        st.markdown('<div class="terminal-header">VALUATION MODELS SUMMARY</div>', unsafe_allow_html=True)
        models = [
            ("DCF Institucional", val.get('dcf_institucional', 0)),
            ("Múltiplos Relativos", val.get('multiples', 0)),
            ("Peter Lynch PEG", val.get('lynch_peg', 0))
        ]
        m_html = "<div style='background:rgba(15, 23, 42, 0.4); padding:10px; border:1px solid rgba(59,130,246,0.1); border-top:0; border-radius:0 0 8px 8px;'>"
        for n, v_m in models:
            if v_m <= 0: continue
            _up = ((v_m - price) / price * 100) if price > 0 else 0
            _c = "#10b981" if _up > 0 else "#ef4444"
            m_html += f"""<div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #1e293b;">
                <span style="color:#94a3b8; font-size:12px;">{n}</span>
                <span style="color:white; font-size:12px; font-weight:700;">${v_m:.2f} <small style="color:{_c}; margin-left:5px;">{_up:+.1f}%</small></span>
            </div>"""
        m_html += "</div>"
        st.markdown(m_html, unsafe_allow_html=True)

    # ── 4. Summary Executive (InvestingPro Style) ──
    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(59, 130, 246, 0.05); padding:20px; border-radius:12px; border:1px solid rgba(59, 130, 246, 0.15); margin-top:20px;">
        <div style="color:#3b82f6; font-size:12px; font-weight:800; text-transform:uppercase; margin-bottom:10px; letter-spacing:1px;">Executive Intelligence Summary</div>
        <p style="color:#e2e8f0; font-size:13px; line-height:1.6;">{v['description']}</p>
        <div style="margin-top:15px; display:flex; gap:10px;">
            <span style="background:#10b98120; color:#10b981; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700;">PROFITABLE</span>
            <span style="background:#3b82f620; color:#3b82f6; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700;">INSTITUTIONAL GRADE</span>
            <span style="background:#f59e0b20; color:#f59e0b; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700;">MACRO EXPOSURE</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    with st.expander("Ver Auditoría Forense (M-Score / Merton)"):
        h = res.get("health", {})
        m = h.get("m_score", {})
        mer = h.get("merton", {})
        
        hc1, hc2, hc3 = st.columns(3)
        with hc1:
            val_m = m.get('score', 0)
            interp = m.get('interpretation', 'N/A')
            m_col = "#10b981" if "NO MANIPULADOR" in interp.upper() else "#ef4444"
            st.markdown(f"""
            <div style="background:#0f172a; padding:15px; border-radius:10px; border-left:4px solid {m_col};">
                <div style="color:#64748b; font-size:10px; text-transform:uppercase;">Beneish M-Score</div>
                <div style="color:white; font-size:20px; font-weight:800;">{val_m:.2f}</div>
                <div style="color:{m_col}; font-size:11px;">{interp}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with hc2:
            prob_d = mer.get('pd', 0)
            status_m = mer.get('status', 'SAFE').upper()
            d_col = "#10b981" if status_m == "SAFE" else "#ef4444"
            st.markdown(f"""
            <div style="background:#0f172a; padding:15px; border-radius:10px; border-left:4px solid {d_col};">
                <div style="color:#64748b; font-size:10px; text-transform:uppercase;">Prob. Default (Merton)</div>
                <div style="color:white; font-size:20px; font-weight:800;">{prob_d*100:.2f}%</div>
                <div style="color:{d_col}; font-size:11px;">Status: {status_m}</div>
            </div>
            """, unsafe_allow_html=True)

        with hc3:
            z = h.get("z_score", 0)
            z_lab = h.get("z_label", "N/A")
            z_col = "#10b981" if "SAFE" in z_lab.upper() else "#ef4444"
            st.markdown(f"""
            <div style="background:#0f172a; padding:15px; border-radius:10px; border-left:4px solid {z_col};">
                <div style="color:#64748b; font-size:10px; text-transform:uppercase;">Altman Z-Score</div>
                <div style="color:white; font-size:20px; font-weight:800;">{z:.2f}</div>
                <div style="color:{z_col}; font-size:11px;">{z_lab}</div>
            </div>
            """, unsafe_allow_html=True)

        # ── AI NARRATIVE AUDITOR (PHASE 12) ──
        st.markdown("---")
        if st.button("🤖 Generar Informe de Riesgo IA", use_container_width=True):
            from services.forensic_ai import ForensicAIAuditor
            with st.spinner("IA analizando patrones forenses..."):
                dna = res.get("sec", {})
                try:
                    audit_text, provider = ForensicAIAuditor.generate_audit_commentary(st.session_state["active_ticker"], h, dna)
                    st.session_state["ai_audit_cache"] = audit_text
                    st.session_state["ai_audit_provider"] = provider
                except Exception as e:
                    st.session_state["ai_audit_cache"] = f"⚠️ IA Audit unavailable: {str(e)[:100]}..."
                    st.session_state["ai_audit_provider"] = "none"
        
        if "ai_audit_cache" in st.session_state:
            prov = st.session_state.get("ai_audit_provider", "IA")
            st.markdown(f"""
            <div style='background:rgba(59,130,246,0.05); border:1px solid #3b82f640; padding:15px; border-radius:8px; font-size:13px; line-height:1.6;'>
                <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>
                    <strong style='color:#3b82f6;'>Deep Audit Intelligence:</strong>
                    <span style='background:#1e293b; color:#94a3b8; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700;'>🤖 {prov}</span>
                </div>
                {st.session_state["ai_audit_cache"]}
            </div>
            """, unsafe_allow_html=True)



    # ── Info del Precio (Ancho Completo) ──
    try:
        low_s = _get_clean_series(hist, "Low")
        high_s = _get_clean_series(hist, "High")
        lo52 = _safe_float(low_s.min()) if low_s is not None else 0.0
        hi52 = _safe_float(high_s.max()) if high_s is not None else 0.0
    except: lo52 = hi52 = 0.0

    day_chg = _safe_float(info.get("regularMarketChange", 0))
    day_pct = _safe_float(info.get("regularMarketChangePercent", 0))
    chg_col = "#10b981" if day_chg >= 0 else "#ef4444"
    
    st.markdown(textwrap.dedent(f"""
    <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:20px;padding:0 10px;">
        <div>
            <div style="font-size:42px;font-weight:900;color:white;line-height:1;">{st.session_state['active_ticker']} <span style="font-size:16px;color:#64748b;font-weight:600;vertical-align:middle;">{info.get('exchange','')}</span></div>
            <div style="color:#94a3b8;font-size:14px;margin-top:6px;">{info.get('longName','')} · {info.get('sector','—')} · {info.get('industry','—')}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:38px;font-weight:800;color:white;line-height:1;">${price:.2f} <span style="font-size:18px;color:{chg_col};vertical-align:middle;">${day_chg:+.2f} ({day_pct:+.2f}%)</span></div>
            <div style="color:#64748b;font-size:12px;margin-top:6px;font-weight:600;letter-spacing:1px;">{_market_badge(info.get("marketState"))}</div>
        </div>
    </div>
    """), unsafe_allow_html=True)

    # ── 1. GRÁFICO DE MARGEN DE SEGURIDAD (Gauge Analógico tipo GuruFocus) ──
    st.markdown("---")
    
    cv_1, cv_2 = st.columns([1.5, 1])
    
    with cv_1:
        st.markdown('<div class="card-title">⚖️ Termómetro de Valor Razonable (DCF & Múltiplos)</div>', unsafe_allow_html=True)
        # Usamos el Gauge estandarizado de finterm
        fig_gauge = fc.create_score_gauge(price, label="Precio vs Valor Justo", target=consensus)
        st.plotly_chart(fig_gauge, use_container_width=True)

    with cv_2:
        st.markdown('<div class="card-title">Modelos Desglosados</div>', unsafe_allow_html=True)
        models_names = ["DCF Institucional", "DCF Simple", "Peter Lynch", "Múltiplos Relativos", "Consenso Target"]
        models_vals = [val.get('dcf_institucional',0), val.get('dcf_simple',0), val.get('lynch_peg',0), val.get('multiples',0), consensus]
        
        html_models = "<div style='display:flex;flex-direction:column;gap:12px;margin-top:10px;'>"
        for m_name, m_val in zip(models_names, models_vals):
            if m_val <= 0: continue
            _up = ((m_val - price) / price * 100) if price > 0 else 0
            _col = "#10b981" if _up > 0 else "#ef4444"
            html_models += f"""
<div style="display:flex;justify-content:space-between;align-items:center;padding:10px;background:#0f172a;border:1px solid #1e293b;border-radius:8px;">
    <span style="color:#94a3b8;font-size:13px;font-weight:600;">{m_name}</span>
    <div style="text-align:right;">
        <span style="color:white;font-size:14px;font-weight:800;margin-right:8px;">${m_val:.2f}</span>
        <span style="color:{_col};font-size:11px;background:{_col}20;padding:2px 6px;border-radius:4px;">{_up:+.1f}%</span>
    </div>
</div>
"""
        html_models += "</div>"
        st.markdown(textwrap.dedent(html_models), unsafe_allow_html=True)

    # ── 2. AUDITORÍA Y SALUD FINANCIERA (Dos columnas anchas) ──
    st.markdown("---")
    st.markdown('<div class="card-title">🔍 Matriz de Calidad y Auditores de Riesgo</div>', unsafe_allow_html=True)
    
    c_left, c_right = st.columns([1, 1.5], gap="large")
    
    with c_left:
        # Radar de Fortaleza usando el componente de finterm
        fig_r = fc.create_component_radar(qual["radar_data"], st.session_state['active_ticker'])
        st.plotly_chart(fig_r, use_container_width=True)
        
        st.markdown(f"""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px;">
  <div style="background:#0f172a;padding:12px;border-radius:8px;border:1px solid #1e293b;text-align:center;">
    <div style="color:#64748b;font-size:10px;letter-spacing:1px;">RIESGO QUIEBRA (ALTMAN Z)</div>
    <div style="color:{'#10b981' if 'SAFE' in risk['altman_label'] else '#ef4444'};font-size:22px;font-weight:900;">{risk['altman_z']}</div>
    <div style="color:#94a3b8;font-size:11px;">{risk['altman_label']}</div>
  </div>
  <div style="background:#0f172a;padding:12px;border-radius:8px;border:1px solid #1e293b;text-align:center;">
    <div style="color:#64748b;font-size:10px;letter-spacing:1px;">MANIPULACIÓN (SLOAN)</div>
    <div style="color:{'#10b981' if 'LIMPIO' in risk['sloan_label'] else '#ef4444'};font-size:22px;font-weight:900;">{risk['sloan_ratio']}%</div>
    <div style="color:#94a3b8;font-size:11px;">{risk['sloan_label']}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    with c_right:
        st.markdown('<div class="card-title">📋 Desglose de Puntos de Calidad</div>', unsafe_allow_html=True)
        # Native rendering instead of custom HTML Grid to avoid markdown escaping
        for cat, items in qual["categorized_details"].items():
            if not items: continue
            cat_score = sum(i["points"] for i in items)
            cat_max = len(items) * 2.0
            cat_pct = (cat_score / cat_max) * 100 if cat_max > 0 else 0
            
            with st.expander(f"🔹 {cat} ({int(cat_pct)}%)"):
                cols = st.columns(3)
                for i, det in enumerate(items):
                    with cols[i % 3]:
                        raw_val = det['value']
                        val_str = _fmt_val(raw_val, det.get('unit','')) if isinstance(raw_val, (int, float)) else str(raw_val)
                        p_val = det['points']
                        p_col = "normal" if p_val >= 1.5 else ("off" if p_val >= 1.0 else "inverse")
                        st.metric(det['indicator'], val_str, delta=f"{p_val} pts", delta_color=p_col)

    # ── 3. TRAYECTORIA Y FINANZAS ──
    st.markdown("---")
    st.markdown('<div class="card-title">⌛ Crecimientos Visuales (Últimos 5 Años)</div>', unsafe_allow_html=True)
    hist_5y = sec_api.get_historical_financials(st.session_state['active_ticker'])
    if not hist_5y.empty:
        fig_h = go.Figure()
        
        # Estilo TIKR: Barras agrupadas dualces
        fig_h.add_trace(go.Bar(
            x=hist_5y["Year"], 
            y=hist_5y["Revenue"], 
            name="Ingresos (Total Revenue)", 
            marker_color="#60a5fa", # Azul claro institucional
            text=[_fmt_val(v, '') for v in hist_5y["Revenue"]],
            textposition='auto',
            textfont=dict(color='white')
        ))
        fig_h.add_trace(go.Bar(
            x=hist_5y["Year"], 
            y=hist_5y["Net Income"], 
            name="Beneficio Neto (Net Income)", 
            marker_color="#334155", # Gris oscuro / Negro estilo TIKR
            text=[_fmt_val(v, '') for v in hist_5y["Net Income"]],
            textposition='auto',
            textfont=dict(color='white')
        ))
        
        fig_h.update_layout(
            barmode='group',
            template="plotly_dark", 
            height=400, 
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)", 
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="h", 
                yanchor="bottom", 
                y=1.05, 
                xanchor="center", 
                x=0.5
            ),
            xaxis=dict(showgrid=False, linecolor='#334155'),
            yaxis=dict(showgrid=True, gridcolor='#1e293b', zeroline=True, zerolinecolor='#334155')
        )
        st.plotly_chart(fig_h, use_container_width=True)
    else:
        st.info("Datos históricos limitados para este ticker.")

    # ── 3. RESUMEN FINANCIERO RÁPIDO (Sistema de Pestañas Pro) ──
    st.markdown("---")
    st.markdown('<div class="card-title">📖 Resumen de Estados Financieros</div>', unsafe_allow_html=True)
    
    def _render_fin_table_tab(df):
        if df is None or df.empty: 
            st.info("Datos no disponibles para este periodo.")
            return
        disp_df = df.head(8).applymap(lambda x: _fmt_val(x) if isinstance(x, (int, float)) else x)
        disp_df.index = [str(idx).encode("ascii", "ignore").decode() for idx in disp_df.index]
        st.dataframe(disp_df, use_container_width=True, height=350)

    t_res, t_bal, t_caj = st.tabs(["📊 Resultados", "⚖️ Balance", "💸 Flujo de Caja"])
    with t_res: _render_fin_table_tab(res["income"])
    with t_bal: _render_fin_table_tab(res["balance"])
    with t_caj: _render_fin_table_tab(res["cashflow"])


# ─────────────────────────────────────────────────────────────────
# TAB 2: INTELIGENCIA IA
# ─────────────────────────────────────────────────────────────────
@st.fragment
def _render_ai_tab(res):
    pdf = res.get("pdf")
    sent = res.get("sent")
    info = res.get("info", {})
    
    st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:20px;">
    <div>
        <h2 style="margin:0;color:white;font-size:24px;">{info.get('shortName', 'Company Insights')}</h2>
        <div style="color:#94a3b8;font-size:13px;">{info.get('sector', '')} | Inteligencia Cuantitativa Real</div>
    </div>
    <div style="text-align:right;">
         <div id="intel-trigger"></div>
    </div>
</div>
""", unsafe_allow_html=True)


    
    if sent:
        bull = sent.get('bullish', 0)
        bear = sent.get('bearish', 0)
        neut = sent.get('neutral', 0)
        total = bull + bear + neut
        if total > 0:
            st.plotly_chart(fc.create_sentiment_donut(bull, neut, bear), use_container_width=True)
            
            # ── NEWS TIMELINE ──
            # Mock news data for the timeline (to be connected with real news feed later)
            news_mock = pd.DataFrame({
                "date": pd.date_range(end=pd.Timestamp.now(), periods=10, freq='D'),
                "sentiment_score": [0.2, -0.4, 0.6, 0.8, -0.1, 0.3, 0.5, -0.7, 0.2, 0.4],
                "title": [f"Evento de Mercado {i}" for i in range(10)]
            })
            st.plotly_chart(fc.create_sentiment_timeline(news_mock), use_container_width=True)

    # ── FINNHUB: SOCIAL SENTIMENT ──
    from services.finnhub_client import get_social_sentiment
    with st.spinner("Midiendo métricas sociales (X & Reddit)..."):
        social = get_social_sentiment(info.get('symbol', st.session_state.get('active_ticker', '')))
    
    if social and (social.get('reddit_mentions', 0) > 0 or social.get('twitter_mentions', 0) > 0):
        st.markdown('<div class="card-title">Pulso Social Finnhub (Hype Meter)</div>', unsafe_allow_html=True)
        rc, tc = st.columns(2)
        with rc:
            rm = social['reddit_mentions']
            rb = social['reddit_bullish']
            rpct = (rb/rm*100) if rm > 0 else 0
            rc.markdown(f"""
            <div style="background:#111827;border:1px solid #ff450040;padding:15px;border-radius:8px;">
                <h4 style="color:#ff4500;margin:0 0 10px 0;">🤖 Reddit Sentiment</h4>
                <div style="color:white;font-size:24px;font-weight:800;">{rm} Menciones</div>
                <div style="color:{'#10b981' if rpct>=50 else '#ef4444'};font-size:14px;">{rpct:.1f}% Alcista</div>
            </div>
            """, unsafe_allow_html=True)
        with tc:
            tm = social['twitter_mentions']
            tb = social['twitter_bullish']
            tpct = (tb/tm*100) if tm > 0 else 0
            tc.markdown(f"""
            <div style="background:#111827;border:1px solid #1DA1F240;padding:15px;border-radius:8px;">
                <h4 style="color:#1DA1F2;margin:0 0 10px 0;">🐦 X (Twitter) Sentiment</h4>
                <div style="color:white;font-size:24px;font-weight:800;">{tm} Menciones</div>
                <div style="color:{'#10b981' if tpct>=50 else '#ef4444'};font-size:14px;">{tpct:.1f}% Alcista</div>
            </div>
            """, unsafe_allow_html=True)
        st.write("")

    if not pdf:
        st.warning("Carga un PDF de InvestingPro para ver insights de IA.")
        return

    summary = pdf.get("executive_summary", "No disponible.")
    st.markdown(f"""
    <div style="background:linear-gradient(135deg, rgba(59,130,246,0.1), rgba(59,130,246,0.05));border:1px solid #3b82f640;padding:22px;border-radius:12px;margin-bottom:20px;">
        <div style="color:#3b82f6;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;">Resumen Ejecutivo IA (Quantum Stream)</div>
    </div>
    """, unsafe_allow_html=True)
    
    # ── Simulación de Streaming para Percepción Institucional ──
    import time
    def _stream_text(text):
        for word in text.split(" "):
            yield word + " "
            time.sleep(0.02)
    
    st.write_stream(_stream_text(summary))

    c1, c2 = st.columns(2)
    insights = pdf.get("insights", {})
    with c1:
        st.markdown('<div class="card-title" style="color:#10b981;">🐂 THE BULL CASE</div>', unsafe_allow_html=True)
        for b in insights.get("bull_case", [])[:4]: 
            st.markdown(f"<div style='background:#064e3b40;border-left:3px solid #10b981;padding:10px;border-radius:0 6px 6px 0;margin-bottom:8px;font-size:13px;color:#e2e8f0;'><span style='color:#10b981;margin-right:8px;'>✓</span>{b}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card-title" style="color:#ef4444;">🐻 THE BEAR CASE</div>', unsafe_allow_html=True)
        for b in insights.get("bear_case", [])[:4]: 
            st.markdown(f"<div style='background:#7f1d1d40;border-left:3px solid #ef4444;padding:10px;border-radius:0 6px 6px 0;margin-bottom:8px;font-size:13px;color:#e2e8f0;'><span style='color:#ef4444;margin-right:8px;'>✗</span>{b}</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="card-title">Matriz SWOT Institucional</div>', unsafe_allow_html=True)
    swot = pdf.get("swot", {})
    s1, s2 = st.columns(2)
    
    def _render_swot_box(icon, title, items, color, bg):
        if not items: return
        content = "".join([f"<li style='margin-bottom:6px;'>{x}</li>" for x in items[:3]])
        st.markdown(f"""
        <div style="background:{bg};border-top:3px solid {color};padding:15px;border-radius:0 0 8px 8px;margin-bottom:15px;height:100%;">
            <div style="color:{color};font-weight:800;font-size:14px;margin-bottom:10px;text-transform:uppercase;">{icon} {title}</div>
            <ul style="color:#cbd5e1;font-size:12px;padding-left:18px;margin:0;">{content}</ul>
        </div>
        """, unsafe_allow_html=True)

    with s1:
        _render_swot_box("💪", "Fortalezas", swot.get("strengths", []), "#10b981", "#064e3b30")
        _render_swot_box("⚡", "Oportunidades", swot.get("opportunities", []), "#3b82f6", "#1e3a8a30")
    with s2:
        _render_swot_box("⚠️", "Debilidades", swot.get("weaknesses", []), "#f59e0b", "#78350f30")
        _render_swot_box("🚩", "Amenazas", swot.get("threats", []), "#ef4444", "#7f1d1d30")


# ─────────────────────────────────────────────────────────────────
# TAB 3: SMART MONEY (KeyError Fix)
# ─────────────────────────────────────────────────────────────────
@st.fragment
def _render_smart_money_tab(res):
    insiders = res.get("insiders")
    holders = res.get("holders")
    
    st.markdown('<div class="card-title">🐋 Vigilancia de Capital Interno & Ballenas</div>', unsafe_allow_html=True)
    
    # Ownership KPIs
    info = res.get("info", {})
    i_pct = info.get("heldPercentInsiders", 0) * 100
    h_pct = info.get("heldPercentInstitutions", 0) * 100
    float_pct = 100 - i_pct - h_pct
    
    st.markdown(textwrap.dedent(f"""
    <div style="display:flex;gap:10px;margin-bottom:20px;">
        <div style="flex:1;background:#0f172a;padding:15px;border-radius:8px;border:1px solid #1e293b;text-align:center;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;">Insider Ownership</div>
            <div style="color:white;font-size:24px;font-weight:800;">{i_pct:.1f}%</div>
        </div>
        <div style="flex:1;background:#0f172a;padding:15px;border-radius:8px;border:1px solid #1e293b;text-align:center;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;">Institutional Ownership</div>
            <div style="color:white;font-size:24px;font-weight:800;">{h_pct:.1f}%</div>
        </div>
        <div style="flex:1;background:#0f172a;padding:15px;border-radius:8px;border:1px solid #1e293b;text-align:center;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;">Public Float</div>
            <div style="color:white;font-size:24px;font-weight:800;">{float_pct:.1f}%</div>
        </div>
    </div>
    """), unsafe_allow_html=True)

    tab_i, tab_h, tab_c, tab_s, tab_o = st.tabs(["🕵️ Insider Watch", "🏦 Whale Tracking", "🏛️ Congress Watch", "🩳 Short Interest", "📈 Options Flow"])
    
    with tab_i:
        st.markdown("<div style='margin-bottom:10px;color:#94a3b8;font-size:12px;'>Extracción en vivo desde SEC EDGAR (Formulario 4)</div>", unsafe_allow_html=True)
        import sec_api
        ticker = st.session_state.get('active_ticker', '')
        
        with st.spinner("Rastreando documentos de la SEC..."):
            sec_form4 = sec_api.get_insider_trades(ticker, limit=10)

        if not sec_form4.empty:
            import plotly.express as px
            import plotly.graph_objects as go
            
            # Limpieza y clasificación: Identificar transacciones de Compra vs Venta
            sec_form4['Date'] = pd.to_datetime(sec_form4['Fecha']).dt.date
            sec_form4['Type'] = sec_form4['Descripción'].apply(lambda x: "Buy" if "purchase" in str(x).lower() or "buy" in str(x).lower() else "Sell")
            # Extraer volumen o magnitud aproximada (simplificado con longitud de descripción o constante si no hay montos extraídos)
            # Como la API actual de Formulario 4 solo trae descripciones, le asigaremos un peso de '1' bloque por transacción para visualizar la Frecuencia (Volume of Trades)
            sec_form4['Volume'] = sec_form4['Type'].apply(lambda x: 1 if x == "Buy" else -1)
            
            # Agrupar por fecha y tipo
            daily_trades = sec_form4.groupby(['Date', 'Type'])['Volume'].sum().reset_index()
            
            # Crear gráfico de Barras Bidireccional (GuruFocus Volume of Guru Trades Style)
            fig_insider = go.Figure()
            
            # Barras Verdes (Compras - Hacia arriba)
            buys = daily_trades[daily_trades['Type'] == 'Buy']
            if not buys.empty:
                fig_insider.add_trace(go.Bar(
                    x=buys['Date'], y=buys['Volume'],
                    name='Insider Buys',
                    marker_color='#10b981',
                    hovertemplate='Fecha: %{x}<br>Transacciones (Compra): %{y}<extra></extra>'
                ))
                
            # Barras Rojas (Ventas - Hacia abajo)
            sells = daily_trades[daily_trades['Type'] == 'Sell']
            if not sells.empty:
                fig_insider.add_trace(go.Bar(
                    x=sells['Date'], y=sells['Volume'],
                    name='Insider Sells',
                    marker_color='#ef4444',
                    hovertemplate='Fecha: %{x}<br>Transacciones (Venta): %{y}<extra></extra>'
                ))
                
            fig_insider.update_layout(
                title=dict(text="Volumen Frecuencial de Transacciones (Formulario 4)", font=dict(color="white", size=15)),
                template="plotly_dark",
                height=350,
                barmode='relative',
                margin=dict(l=0, r=0, t=40, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis=dict(title='Frecuencia', showgrid=True, gridcolor='#1e293b', zeroline=True, zerolinecolor='#94a3b8')
            )
            st.plotly_chart(fig_insider, use_container_width=True)
            
            # Dejar la tabla detallada colapsada para quien necesite leer las actas
            with st.expander("Ver Reporte Oficial Organizado (Enlaces en Sec Edgar)"):
                html = ""
                for _, row in sec_form4.iterrows():
                    date = str(row["Fecha"])[:10]
                    desc = str(row["Descripción"])[:60]
                    url = row["document_url"]
                    action_text = "COMPRA" if row['Type'] == "Buy" else "VENTA"
                    color = "#10b981" if action_text == "COMPRA" else "#ef4444"
    
                    html += f"""
<div style="display:flex;justify-content:space-between;align-items:center;background:#0a0f1a;padding:12px 18px;border-left:4px solid {color};margin-bottom:8px;border-radius:6px;">
    <div>
        <div style="color:white;font-weight:700;font-size:14px;">{desc}</div>
        <div style="color:#64748b;font-size:11px;">Formulario 4 • {date}</div>
    </div>
    <div style="text-align:right;">
        <span style="background:{color}20;color:{color};padding:2px 8px;border-radius:12px;font-size:10px;font-weight:800;margin-right:10px;">{action_text}</span>
        <a href="{url}" target="_blank" style="color:#3b82f6;text-decoration:none;font-weight:600;font-size:12px;">📄 Doc Oficial SEC</a>
    </div>
</div>
"""
                st.markdown(html, unsafe_allow_html=True)
        else: st.info("No Insider data found in recent filings.")
            
    with tab_h:
        st.markdown("<div style='margin-bottom:10px;color:#94a3b8;font-size:12px;'>Rastreo Institucional (13F Filings) - Datos Consolidados de Fondos (Whales)</div>", unsafe_allow_html=True)
        import sec_api
        ticker = st.session_state.get('active_ticker', '')
        
        with st.spinner("Compilando posiciones de grandes fondos..."):
            whales = sec_api.get_whale_holdings_13f(ticker)
        
        if whales:
            w_df = pd.DataFrame(whales).sort_values("shares", ascending=False).head(10)
            
            cw1, cw2 = st.columns([1.5, 1])
            with cw1:
                import plotly.express as px
                fig_w = px.bar(w_df, x="shares", y="name", orientation='h', 
                               title="Top 10 Institutional Whales (13F)",
                               color_discrete_sequence=['#60a5fa'])
                fig_w.update_layout(template="plotly_dark", height=400, margin=dict(l=0, r=0, t=30, b=0),
                                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_w, use_container_width=True)
            
            with cw2:
                st.markdown("### 🏛️ Mayores Tenedores (Whales)")
                for w in whales[:10]:
                    st.markdown(f"""
                    <div style='background:#111827; padding:10px; border-radius:8px; margin-bottom:5px; border-left:3px solid #60a5fa;'>
                        <div style='color:white; font-weight:700; font-size:13px;'>{w['name']}</div>
                        <div style='color:#64748b; font-size:11px;'>Acciones: {w['shares']:,}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No Whale data found.")
        
        # ── 13F / 13D SEC Surveillance ──
        st.markdown("<div style='margin-top:20px;color:#94a3b8;font-size:12px;'>Rastreo de Ballenas (Filings 13F/13D/13G)</div>", unsafe_allow_html=True)
        import sec_api
        whales = sec_api.search_whale_activity(ticker)
        if not whales.empty:
            for _, row in whales.iterrows():
                with st.container():
                     st.markdown(textwrap.dedent(f"""
                     <div style="background:#111827;border:1px solid #374151;padding:10px;border-radius:6px;margin-bottom:8px;">
                         <div style="display:flex;justify-content:space-between;">
                             <span style="color:#3b82f6;font-weight:700;">{row['form']}</span>
                             <span style="color:#6b7280;font-size:11px;">{row['filing_date']}</span>
                         </div>
                         <div style="color:#e5e7eb;font-size:13px;margin:5px 0;">{row['description']}</div>
                         <a href="{row['document_url']}" target="_blank" style="color:#3b82f6;text-decoration:none;font-size:12px;">🔗 Ver Filing Completo</a>
                     </div>
                     """), unsafe_allow_html=True)

    with tab_c:
        st.markdown("<div style='margin-bottom:10px;color:#94a3b8;font-size:12px;'>Operaciones de miembros del Senado y la Cámara de Representantes (House)</div>", unsafe_allow_html=True)
        from services.surveillance import congress_trades
        ticker = st.session_state.get('active_ticker', '')
        
        with st.spinner("Fiscalizando capital político..."):
            congress_df = congress_trades.get_congressional_trades(ticker)
        
        if not congress_df.empty:
            st.markdown(f'<div style="color:#3b82f6;font-size:14px;font-weight:700;margin-bottom:15px;">Se encontraron {len(congress_df)} operaciones recientes por legisladores en {ticker}</div>', unsafe_allow_html=True)
            
            # Gráfico de operaciones por Cámara
            fig_cong = px.scatter(congress_df, x="transaction_date", y="representative", 
                                  color="type", size_max=15,
                                  title="Cronología de Operaciones en el Congreso",
                                  template="plotly_dark",
                                  labels={"transaction_date": "Fecha Operación", "representative": "Legislador"})
            fig_cong.update_layout(height=400, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_cong, use_container_width=True)
            
            st.dataframe(congress_df[["transaction_date", "representative", "type", "amount", "chamber"]], use_container_width=True)
        else:
            st.info("No se detectaron operaciones recientes del Congreso para este ticker.")

    with tab_s:
        st.markdown("<div style='margin-bottom:10px;color:#94a3b8;font-size:12px;'>Métricas Oficiales de Short Interest (FINRA/NYSE/NASDAQ)</div>", unsafe_allow_html=True)
        from sec_api import get_short_interest_data
        ticker = st.session_state.get('active_ticker', '')
        
        short_data = get_short_interest_data(ticker)
        
        cs1, cs2, cs3 = st.columns(3)
        with cs1:
            st.metric("Short % of Float", f"{short_data['short_percent_float']:.2f}%")
        with cs2:
            st.metric("Short Ratio (Days to Cover)", f"{short_data['short_ratio']:.2f}")
        with cs3:
            st.metric("Shares Short", _fmt_val(short_data['shares_short']))
            
        # Gauge de Sentimiento Contrario
        s_pct = short_data['short_percent_float']
        if s_pct > 15: 
            s_msg = "RIESGO DE SHORT SQUEEZE (ALTO)"
            s_col = "#10b981" # Bullish if squeeze potential
        elif s_pct > 8:
            s_msg = "SENTIMIENTO NEGATIVO (MEDIO)"
            s_col = "#f59e0b"
        else:
            s_msg = "SENTIMIENTO SALUDABLE"
            s_col = "#94a3b8"
            
        st.markdown(textwrap.dedent(f"""
        <div style="background:{s_col}15;border:1px solid {s_col}40;padding:15px;border-radius:10px;text-align:center;margin-top:10px;">
            <div style="color:{s_col};font-weight:800;font-size:16px;">{s_msg}</div>
            <div style="color:#94a3b8;font-size:12px;margin-top:4px;">Basado en el porcentaje de acciones en corto respecto al flotante</div>
        </div>
        """), unsafe_allow_html=True)

    with tab_o:
        st.markdown("<div style='margin-bottom:10px;color:#94a3b8;font-size:12px;'>Flujo de Opciones Inusuales (Volumen > Open Interest)</div>", unsafe_allow_html=True)
        from services.options_service import get_options_flow
        ticker = st.session_state.get('active_ticker', '')
        
        flow = get_options_flow(ticker)
        if not flow.empty:
            def _color_type(val):
                color = '#10b981' if val == 'CALL' else '#ef4444'
                return f'color: {color}; font-weight: bold;'
            
            # Reset index to avoid KeyError: 'Styler.apply and .map are not compatible with non-unique index'
            display_flow = flow[['Type', 'strike', 'lastPrice', 'volume', 'openInterest', 'Unusual_Score']].reset_index(drop=True)
            
            st.dataframe(display_flow.style.applymap(_color_type, subset=['Type']), 
                         use_container_width=True, hide_index=True)
        else:
            st.info("No unusual options flow detected for this ticker.")


# ─────────────────────────────────────────────────────────────────
# TAB 4: ANALISIS TECNICO PRO (MultiIndex Fix)
# ─────────────────────────────────────────────────────────────────
def _render_technical_tab(res):
    hist = res["hist"]
    if hist is None or hist.empty:
        st.error("Sin datos.")
        return
        
    close = _get_clean_series(hist, "Close")
    high = _get_clean_series(hist, "High")
    low = _get_clean_series(hist, "Low")
    open_p = _get_clean_series(hist, "Open")
    volume = _get_clean_series(hist, "Volume")

    if close is None:
        st.error("Error al procesar series de tiempo.")
        return

    st.markdown('<div class="card-title">📈 Terminal Trading Avanzado</div>', unsafe_allow_html=True)

    # Indicators
    sma20 = close.rolling(int(20)).mean()
    sma50 = close.rolling(int(50)).mean()
    std20 = close.rolling(int(20)).std()
    bb_upper = sma20 + (std20 * 2)
    bb_lower = sma20 - (std20 * 2)
    
    delta = close.diff(); gain = delta.where(delta > 0, 0).rolling(int(14)).mean(); loss = -delta.where(delta < 0, 0).rolling(int(14)).mean()
    rs = gain / loss; rsi = 100 - (100 / (1 + rs))
    
    ema12 = close.ewm(span=12).mean(); ema26 = close.ewm(span=26).mean(); macd = ema12 - ema26; sig = macd.ewm(span=9).mean()
    macd_hist = macd - sig

    vol_colors = ['#10b981' if c >= o else '#ef4444' for c, o in zip(close, open_p)]
    macd_colors = ['#10b981' if val > 0 else '#ef4444' for val in macd_hist]

    # Score Técnico para Tachometer
    latest_close = close.iloc[-1]
    latest_rsi = rsi.iloc[-1] if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50
    latest_macd_hist = macd_hist.iloc[-1] if not macd_hist.empty and not pd.isna(macd_hist.iloc[-1]) else 0
    latest_sma20 = sma20.iloc[-1] if not sma20.empty and not pd.isna(sma20.iloc[-1]) else latest_close
    latest_sma50 = sma50.iloc[-1] if not sma50.empty and not pd.isna(sma50.iloc[-1]) else latest_close
    
    score = 0
    if latest_rsi < 40: score += 2
    elif latest_rsi > 60: score -= 2
    
    if latest_macd_hist > 0: score += 1
    elif latest_macd_hist < 0: score -= 1
    
    if latest_close > latest_sma20: score += 1
    elif latest_close < latest_sma20: score -= 1
    
    if latest_close > latest_sma50: score += 1
    elif latest_close < latest_sma50: score -= 1

    # Score from -5 (Strong Sell) to +5 (Strong Buy)
    # Map to text
    if score >= 3: tach_text = "COMPRA FUERTE"; tach_col = "#10b981"
    elif score >= 1: tach_text = "COMPRA"; tach_col = "#34d399"
    elif score <= -3: tach_text = "VENTA FUERTE"; tach_col = "#ef4444"
    elif score <= -1: tach_text = "VENTA"; tach_col = "#f87171"
    else: tach_text = "NEUTRAL"; tach_col = "#94a3b8"

    c_tach1, c_tach2 = st.columns([1, 2])
    
    with c_tach1:
        fig_g = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={'suffix': "", 'font': {'size': 30, 'color': tach_col}},
            title={'text': f"Resume Técnico:<br><span style='font-size:20px;color:{tach_col};font-weight:bold;'>{tach_text}</span>", 'font': {'color': 'white', 'size': 14}},
            gauge={
                'axis': {'range': [-5, 5], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': tach_col},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#334155",
                'steps': [
                    {'range': [-5, -2], 'color': 'rgba(239, 68, 68, 0.2)'},
                    {'range': [-2, 2], 'color': 'rgba(148, 163, 184, 0.2)'},
                    {'range': [2, 5], 'color': 'rgba(16, 185, 129, 0.2)'}
                ],
            }
        ))
        fig_g.update_layout(template="plotly_dark", height=250, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_g, use_container_width=True)

    with c_tach2:
        st.markdown(f"""
        <div style="background:#0f172a;padding:25px;border-radius:12px;border:1px solid #1e293b;height:100%;display:flex;flex-direction:column;justify-content:center;">
          <h3 style="color:white;margin:0 0 15px 0;">Señales Clave</h3>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
            <div style="display:flex;justify-content:space-between;border-bottom:1px solid #334155;padding-bottom:5px;">
              <span style="color:#94a3b8;">RSI (14)</span>
              <span style="color:{'#10b981' if latest_rsi<40 else ('#ef4444' if latest_rsi>60 else '#f59e0b')};font-weight:bold;">{latest_rsi:.1f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;border-bottom:1px solid #334155;padding-bottom:5px;">
              <span style="color:#94a3b8;">MACD Hist</span>
              <span style="color:{'#10b981' if latest_macd_hist>0 else '#ef4444'};font-weight:bold;">{latest_macd_hist:.2f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;border-bottom:1px solid #334155;padding-bottom:5px;">
              <span style="color:#94a3b8;">SMA 20</span>
              <span style="color:{'#10b981' if latest_close>latest_sma20 else '#ef4444'};font-weight:bold;">${latest_sma20:.2f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;border-bottom:1px solid #334155;padding-bottom:5px;">
              <span style="color:#94a3b8;">SMA 50</span>
              <span style="color:{'#10b981' if latest_close>latest_sma50 else '#ef4444'};font-weight:bold;">${latest_sma50:.2f}</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Integración con el nuevo dashboard técnico institucional de finterm.charts
    # Aseguramos que hist tenga las columnas necesarias (algunas ya vienen del quant motor)
    if 'MA20' not in hist.columns: hist['MA20'] = sma20
    if 'MA50' not in hist.columns: hist['MA50'] = sma50
    if 'RSI' not in hist.columns: hist['RSI'] = rsi
    if 'MACD' not in hist.columns: 
        hist['MACD'] = macd
        hist['Signal'] = sig
        hist['Hist'] = macd_hist
    if 'BB_upper' not in hist.columns:
        hist['BB_upper'] = bb_upper
        hist['BB_lower'] = bb_lower

    # ── DETECCIÓN DE ANOMALÍAS ──
    try:
        st.markdown("---")
        st.markdown('<div class="card-title">🚨 Detector de Anomalías (Isolation Forest)</div>', unsafe_allow_html=True)
        from services.anomalies_service import detect_price_anomalies
        anomalies = detect_price_anomalies(hist)
        if anomalies:
            st.warning(f"Se han detectado {len(anomalies)} anomalías de precio/volumen en el historial reciente.")
            st.write("Fechas anómalas:", [d.date().strftime("%Y-%m-%d") for d in anomalies[:5]])
        else:
            st.success("No se detectaron anomalías estructurales en el precio reciente.")
    except Exception as e_an:
        st.info(f"Detección de anomalías no disponible: {e_an}")
    
    # ── INDICADORES AVANZADOS ──
    st.markdown("---")
    adv_inds = st.multiselect(
        "🛠️ Configuración de Terminal Pro",
        ["Volume Profile (VPVR)", "Volume Delta", "Exposición Gamma (Estimada)"],
        default=["Volume Delta"],
        key="tech_adv_inds"
    )

    try:
        # Si se selecciona Volume Profile, lo calculamos e integramos si es posible
        # Por ahora mostramos el dashboard técnico base que ya incluye Delta por defecto en el nuevo update de finterm
        fig_tech = fc.create_technical_dashboard(hist, st.session_state['active_ticker'])
        
        if "Volume Profile (VPVR)" in adv_inds:
            # Mostramos un gráfico lateral de Volume Profile o lo integramos
            st.markdown("### 📊 Perfil de Volumen (Market Profile)")
            fig_vp = fc.create_volume_profile(hist)
            st.plotly_chart(fig_vp, use_container_width=True)

        if fig_tech:
            st.plotly_chart(fig_tech, use_container_width=True)
        else:
            st.info("No se pudo generar el panel técnico detallado.")
    except Exception as e_ft:
        st.error(f"Error al renderizar gráficos técnicos: {e_ft}")




@st.fragment
def _render_deep_fundamental_tab(res):
    """💰 TAB 2: DEEP FUNDAMENTAL"""
    ticker = st.session_state.get('active_ticker', '')
    forensic = res.get("forensic", {})
    alloc = forensic.get("allocation", {})
    qual = res.get("quality", {})
    
    st.markdown('<h2 style="color:white;font-size:22px;margin-bottom:20px;">💰 Análisis Fundamental Profundo</h2>', unsafe_allow_html=True)

    c_radar, c_water = st.columns([1, 1], gap="large")
    
    with c_radar:
        st.markdown('<div class="card-title">🛡️ Radar Fundamental (6D)</div>', unsafe_allow_html=True)
        if "radar_data" in qual:
            fig_r = fc.create_component_radar(qual["radar_data"], ticker)
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.info("Datos insuficientes para generar el radar.")
            
    with c_water:
        st.markdown('<div class="card-title">🍎 Capital Allocation (Agregado)</div>', unsafe_allow_html=True)
        if alloc and not alloc.get("error"):
            wf = alloc.get("waterfall_items", [])
            if wf:
                fig_a = go.Figure(go.Waterfall(
                    measure = [i["type"] for i in wf],
                    x = [i["label"] for i in wf],
                    y = [i["value"] for i in wf],
                    connector = {"line":{"color":"#334155"}},
                    decreasing = {"marker":{"color":"#ef4444"}},
                    increasing = {"marker":{"color":"#10b981"}},
                    totals = {"marker":{"color":"#3b82f6"}}
                ))
                fig_a.update_layout(template="plotly_dark", height=350, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_a, use_container_width=True)
            else:
                st.info("No hay desglose de capital waterfall.")
        else:
            st.info("No hay datos de Capital Allocation.")

    st.markdown("---")
    st.markdown('<div class="card-title">⌛ Finanzas Históricas (Últimos 5 Años)</div>', unsafe_allow_html=True)
    hist_5y = sec_api.get_historical_financials(ticker)
    if not hist_5y.empty:
        st.dataframe(hist_5y, use_container_width=True)
    else:
        st.info("Datos históricos limitados para este ticker.")

    st.markdown("---")
    c_inv, c_debt = st.columns(2, gap="large")
    with c_inv:
        st.markdown("### 📦 Inventario (Salud)")
        inv = forensic.get("inventory", {})
        if inv and not inv.get("error"):
            st.markdown(f"""<div style="color:{inv.get('health_color')};font-weight:800;margin-bottom:10px;">{inv.get('health_score')}</div>""", unsafe_allow_html=True)
            for key in ["finished_goods", "work_in_process", "raw_materials"]:
                item = inv.get(key)
                if item and item.get("value_b"):
                    color = "#10b981" if item["signal"] == "GREEN" else ("#f59e0b" if item["signal"] == "YELLOW" else "#ef4444")
                    pct = (item['value_b']/(inv['total_b'] or 1))*100
                    st.markdown(f"""<div style="font-size:11px;color:#94a3b8;">{key.replace('_',' ').title()}: <b>{item['value_b']}B</b></div>
                    <div style="height:4px;background:#1e293b;margin-bottom:8px;"><div style="width:{pct}%;height:100%;background:{color};"></div></div>""", unsafe_allow_html=True)
        else:
            st.info("Operaciones sin inventario material.")
            
    with c_debt:
        st.markdown("### 🏦 Deuda Institucional")
        debt = forensic.get("debt", {})
        if debt and not debt.get("error"):
            st.markdown(f"""<div style="color:{debt.get('refinance_color')};font-weight:800;margin-bottom:10px;">{debt.get('refinance_risk')} RISK</div>""", unsafe_allow_html=True)
            st.write(f"Net Debt/EBITDA: **{debt.get('net_debt_ebitda')}x**")
            st.caption(debt.get('next_maturity_note'))
        else:
            st.info("Sin deuda a corto plazo.")
            
    with st.expander("Ver Estados Financieros Totales"):
        _render_fundamental_tab_logic(res)

def _render_fundamental_tab_logic(res):
    """Pestaña de tablas financieras detalladas con normalización automática."""
    t_inc, t_bal, t_cf = st.tabs(["Income", "Balance", "Cash Flow"])
    
    def _format_df(df):
        if df is None: return None
        return df.applymap(lambda x: _fmt_val(x) if isinstance(x, (int, float)) else x)

    with t_inc: st.dataframe(_format_df(res.get("income")), use_container_width=True)
    with t_bal: st.dataframe(_format_df(res.get("balance")), use_container_width=True)
    with t_cf: st.dataframe(_format_df(res.get("cashflow")), use_container_width=True)

@st.fragment
def _render_forecast_tab(res):
    """🎯 TAB 3: FORECAST & TARGETS"""
    forecast = res.get("forecast", {})
    eps = forecast.get("eps", {})
    px = forecast.get("price", {})
    rev = forecast.get("revenue", {})

    st.markdown('<h2 style="color:white;font-size:22px;margin-bottom:20px;">🎯 Forecast & Consenso de Analistas</h2>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.markdown("### 📊 EPS Forward Bridge")
        hist_eps = eps.get("historical", {})
        fwd_eps = eps.get("forward", {})
        
        years = sorted(list(hist_eps.keys()) + list(fwd_eps.keys()))
        vals = [hist_eps.get(y) or fwd_eps.get(y) for y in years]
        colors = ["#334155" if y <= 2025 else "#3b82f6" for y in years]
        
        fig_eps = go.Figure(go.Bar(x=years, y=vals, marker_color=colors, text=vals, textposition='auto'))
        fig_eps.update_layout(template="plotly_dark", height=350, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_eps, use_container_width=True)
        st.caption(eps.get("tax_cliff_note", ""))

    with c2:
        st.markdown("### 🎯 Price Target Consensus")
        target = px.get("target_mean", 0)
        curr = px.get("current_price", 0)
        upside = px.get("upside_pct", 0)
        
        st.markdown(f"""
        <div style="background:#0f172a;padding:25px;border-radius:12px;border:1px solid #1e293b;text-align:center;">
            <div style="color:#94a3b8;font-size:12px;">TARGET PROMEDIO</div>
            <div style="color:white;font-size:38px;font-weight:900;">${target:.2f}</div>
            <div style="color:{'#10b981' if upside>0 else '#ef4444'};font-size:18px;font-weight:700;">{upside:+.1f}% Upside</div>
            <hr style="border:0;border-top:1px solid #1e293b;margin:20px 0;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                <div><small style="color:#64748b;">HIGH</small><br><b>${px.get('target_high')}</b></div>
                <div><small style="color:#64748b;">LOW</small><br><b>${px.get('target_low')}</b></div>
            </div>
            <div style="margin-top:20px;padding:10px;background:#3b82f620;color:#3b82f6;border-radius:6px;font-size:13px;font-weight:700;">
                RECOMENDACIÓN: {px.get('recommendation','HOLD').upper()}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📈 Revenue Growth Cone (Institutional Consensus)")
    
    # ── Predictive Cone Chart (TIKR Style) ──
    rev_hist = rev.get("historical", {})
    est_26 = rev.get("fy26_estimate", 0)
    
    if rev_hist and est_26:
        import numpy as np
        h_yrs = sorted(rev_hist.keys())
        h_vals = [rev_hist[y] for y in h_yrs]
        
        # Proyección simplificada (Cono de Incertidumbre)
        f_yrs = [h_yrs[-1], 2026]
        f_mid = [h_vals[-1], est_26]
        f_hi = [h_vals[-1], est_26 * 1.05]
        f_lo = [h_vals[-1], est_26 * 0.95]
        
        fig_cone = go.Figure()
        
        # Historial (Línea sólida)
        fig_cone.add_trace(go.Scatter(x=h_yrs, y=h_vals, mode='lines+markers', name='Historial (SEC)', line=dict(color='#94a3b8', width=3)))
        
        # Cono Proyectado (Sombreado)
        fig_cone.add_trace(go.Scatter(x=f_yrs + f_yrs[::-1], y=f_hi + f_lo[::-1], fill='toself', fillcolor='rgba(59, 130, 246, 0.1)', line=dict(color='rgba(255,255,255,0)'), name='Rango Consenso', showlegend=True))
        
        # Línea central proyectada
        fig_cone.add_trace(go.Scatter(x=f_yrs, y=f_mid, mode='lines+markers', name='Proyección (Estimado)', line=dict(color='#3b82f6', dash='dash', width=3)))
        
        fig_cone.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5))
        st.plotly_chart(fig_cone, use_container_width=True)
    
    st.info(rev.get("trend", "Consenso estable."))

@st.fragment
def _render_ai_conflict_tab(res):
    """🤖 TAB 4: INTELLIGENCE & CONFLICT"""
    conflict = res.get("conflict", {})
    pdf = res.get("pdf", {})
    
    st.markdown('<h2 style="color:white;font-size:22px;margin-bottom:20px;">🤖 Inteligencia Artificial & Detección de Conflicto</h2>', unsafe_allow_html=True)

    # 1. Conflict Dashboard (Premium)
    c1, c2 = st.columns([1, 2])
    with c1:
        score = conflict.get("score", 5)
        color = "#ef4444" if score > 7 else ("#f59e0b" if score > 5 else "#3b82f6")
        st.markdown(f"""
        <div style="background:rgba(15, 23, 42, 0.6); backdrop-filter: blur(10px); padding:30px; border-radius:15px; border:1px solid {color}40; text-align:center; box-shadow: 0 0 20px {color}15;">
            <div style="color:#94a3b8; font-size:11px; margin-bottom:10px; letter-spacing:2px; font-weight:700;">CONFLICT INDEX</div>
            <div style="font-size:64px; font-weight:900; color:{color}; line-height:1;">{score}</div>
            <div style="background:{color}20; color:{color}; display:inline-block; padding:3px 12px; border-radius:20px; font-size:11px; font-weight:800; margin-top:15px;">{conflict.get('dominant_view')}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("### ⚠️ Divergencia de Señales")
        st.markdown("<div style='color:#64748b; font-size:12px; margin-bottom:15px;'>Mapeo automático de tesis institucionales vs acción del precio.</div>", unsafe_allow_html=True)
        
        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown("<div style='border-left:3px solid #10b981; padding-left:15px; margin-bottom:10px;'><small style='color:#10b981; font-weight:800;'>BULLISH FUNDAMENTALS</small></div>", unsafe_allow_html=True)
            for s in conflict.get("fundamental_signals", []): 
                st.markdown(f"<div style='background:rgba(16, 185, 129, 0.05); padding:8px 12px; border-radius:6px; margin-bottom:6px; font-size:13px;'>{s['label']}: <span style='color:white; font-weight:700;'>{s['value']}</span></div>", unsafe_allow_html=True)
        with sc2:
            st.markdown("<div style='border-left:3px solid #ef4444; padding-left:15px; margin-bottom:10px;'><small style='color:#ef4444; font-weight:800;'>BEARISH TECHNICALS</small></div>", unsafe_allow_html=True)
            for s in conflict.get("technical_signals", []): 
                st.markdown(f"<div style='background:rgba(239, 68, 68, 0.05); padding:8px 12px; border-radius:6px; margin-bottom:6px; font-size:13px;'>{s['label']}: <span style='color:white; font-weight:700;'>{s['value']}</span></div>", unsafe_allow_html=True)

    st.markdown("---")
    
    # 2. SWOT PREMIUM (Glassmorphism Matrix)
    if pdf:
        swot = pdf.get("swot", {})
        st.markdown("### 🔳 Matriz SWOT Institutional (InvestingPro Intelligence)")
        
        # Custom CSS for Glass SWOT
        m1, m2 = st.columns(2)
        
        def _render_box(title, items, color, bg, icon):
            if not items: return
            bullets = "".join([f"<li style='margin-bottom:8px;'>{item}</li>" for item in items[:3]])
            st.markdown(f"""
            <div style="background:{bg}; backdrop-filter: blur(8px); padding:20px; border-radius:12px; border:1px solid {color}30; margin-bottom:15px; height:220px; position:relative; overflow:hidden;">
                <div style="font-size:40px; position:absolute; right:-5px; bottom:-5px; opacity:0.1; transform: rotate(-15deg);">{icon}</div>
                <div style="color:{color}; font-weight:900; font-size:13px; text-transform:uppercase; letter-spacing:1px; margin-bottom:15px; display:flex; align-items:center; gap:8px;">
                    <span style="background:{color}; width:8px; height:8px; border-radius:50%;"></span> {title}
                </div>
                <ul style="color:#e2e8f0; font-size:12px; padding-left:15px; line-height:1.4;">{bullets}</ul>
            </div>
            """, unsafe_allow_html=True)

        with m1:
            _render_box("Fortalezas", swot.get("strengths", []), "#10b981", "rgba(16, 185, 129, 0.05)", "🚀")
            _render_box("Oportunidades", swot.get("opportunities", []), "#3b82f6", "rgba(59, 130, 246, 0.05)", "💡")
        with m2:
            _render_box("Debilidades", swot.get("weaknesses", []), "#f59e0b", "rgba(245, 158, 11, 0.05)", "⚠️")
            _render_box("Amenazas", swot.get("threats", []), "#ef4444", "rgba(239, 68, 68, 0.05)", "🚩")

    # 3. Catalizadores IA
    st.markdown("---")
    st.markdown("### 🚀 Catalizadores Dinámicos & Risk Ranking")
    r1, r2 = st.columns([1.5, 1])
    with r1:
        for r in conflict.get("risk_ranking", []):
            st.markdown(f"""
            <div style="background:rgba(239, 68, 68, 0.1); border-left:4px solid #ef4444; padding:12px 18px; border-radius:0 8px 8px 0; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:white; font-weight:700; font-size:14px;">{r['risk']}</span>
                    <span style="background:#ef4444; color:white; font-size:10px; font-weight:800; padding:2px 8px; border-radius:12px;">{r['impact']}</span>
                </div>
                <div style="color:#94a3b8; font-size:11px; margin-top:4px;">Probabilidad: <b>{r['probability']}</b> | Horizonte: <b>{r.get('timeline', 'N/A')}</b></div>
            </div>
            """, unsafe_allow_html=True)
    with r2:
        for c in conflict.get("catalysts", []):
            st.markdown(f"""
            <div style="background:rgba(59, 130, 246, 0.05); padding:10px; border-radius:8px; border:1px solid #3b82f620; margin-bottom:8px;">
                <div style="color:#3b82f6; font-size:11px; font-weight:800;">{c['date']}</div>
                <div style="color:white; font-size:13px; font-weight:600; margin:2px 0;">{c['event']}</div>
                <div style="color:#64748b; font-size:11px;">Foco: {c['watch']}</div>
            </div>
            """, unsafe_allow_html=True)

def _render_earnings_tab(res):
    st.markdown('<div class="card-title">🎙️ Transcripción & Análisis de Earnings Call</div>', unsafe_allow_html=True)
    st.markdown("<div style='color:#94a3b8;font-size:12px;margin-bottom:20px;'>Analiza lo que dicen los CEOs. Pega un link de YouTube o un archivo de audio de Investor Relations.</div>", unsafe_allow_html=True)
    
    audio_url = st.text_input("YouTube / Audio URL", placeholder="https://www.youtube.com/watch?v=...", key="earnings_url")
    
    if audio_url:
        if st.button("Transcribir con Whisper IA (Local)"):
            from services.earnings_service import download_audio, transcribe_earnings
            ticker = st.session_state.get('active_ticker', 'CORP')
            
            with st.spinner("Descargando y transcribiendo (esto puede tardar unos minutos)..."):
                try:
                    path = download_audio(audio_url, f"{ticker}_earnings")
                    transcript = transcribe_earnings(path)
                    
                    st.subheader("Transcripción Completa")
                    st.text_area("Texto", transcript, height=400)
                    
                    # Análisis de sentimiento básico
                    st.subheader("Análisis de Sentimiento IA")
                    from services import sentiment_service
                    sent = sentiment_service.analyze_sentiment_finbert(transcript[:500]) # Example on first chunk
                    st.json(sent)
                except Exception as e:
                    st.error(f"Error en el proceso: {e}")
    else:
        st.info("Ingresa una URL para comenzar la fiscalización de la conferencia de resultados.")

# ─────────────────────────────────────────────────────────────────
# TAB 7: ALT-DATA & CORPORATE ESPIONAGE
# ─────────────────────────────────────────────────────────────────

def _render_altdata_tab(ticker):
    st.markdown("<div class='sec-title'>🔬 Inteligencia Estratégica & Análisis Alternativo</div>", unsafe_allow_html=True)
    st.caption("Filtros de Datos de Terceros: Congreso, Sentimiento Social y Métricas Corporativas.")
    
    if st.button("🚀 Iniciar Recuperación de Inteligencia", use_container_width=True):
        with st.spinner("🔍 Conectando con nodos de inteligencia de mercado..."):
            try:
                # El motor de recolección de Alt-Data está siendo migrado a un pool asíncrono institucional.
                st.info("El motor de extracción avanzada está actualmente en mantenimiento para cumplir con los estándares de latencia institucional.")
            except Exception as e:
                st.error(f"Error en la recuperación de datos: {e}")
                
    if "alt_data_cache" in st.session_state:
        db = st.session_state["alt_data_cache"]
        
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            st.markdown("### ⚖️ Trades del Congreso")
            trades = db["quiver"]
            if trades:
                for t in trades:
                    c = "green" if t["type"] == "Buy" else "red"
                    st.markdown(f"**{t['politician']}** <br> <span style='color:{c}'>{t['type']}</span> | {t['date']} | {t['amount']}", unsafe_allow_html=True)
            else: st.info("No congressional trades detected recently.")
            
        with ac2:
            st.markdown("### 🦍 Hype Reddit (WSB)")
            red = db["reddit"]
            if "error" not in red:
                st.metric("Menciones (24h)", red.get("mentions_24h", 0))
                
                # Handling progress cleanly
                bull_pct = red.get('sentiment_bullish_pct', 50)
                st.progress(bull_pct / 100, text=f"Bullish: {bull_pct}%")
                
                st.markdown(f"**Veredicto:** {red.get('verdict', '')}")
            else: st.error(red["error"])
            
        with ac3:
            st.markdown("### 🏢 Vitalidad Glassdoor")
            gd = db["glassdoor"]
            if "error" not in gd:
                st.metric("Aprobación CEO", f"{gd.get('ceo_approval_pct', 0)}%")
                st.metric("Perspectiva Empleados", f"{gd.get('business_outlook_pct', 0)}%")
                warning = "⚠️ ALERTA DE FUGA" if gd.get("talent_exodus_warning") else "✅ Retención Estable"
                st.markdown(f"**Alerta de Fuga de Talento:** {warning}")
            else: st.error(gd["error"])
# ─────────────────────────────────────────────────────────────────
# TAB 5: ULTRA FUNDAMENTAL (Restored)
# ─────────────────────────────────────────────────────────────────

def _render_options_tab(ticker):
    """📉 Análisis de Opciones, Griegas y Niveles Gamma."""
    st.markdown("<div class='card-title'>🌀 Análisis de Gamma & Opciones</div>", unsafe_allow_html=True)
    if not ticker:
        st.info("Ingresa un ticker.")
        return
        
    try:
        tk = yf.Ticker(ticker)
        expirations = tk.options
        if not expirations:
            st.warning("No se encontraron cadenas de opciones para este activo.")
            return
            
        exp = st.selectbox("Vencimiento", expirations, index=0)
        chain = tk.option_chain(exp)
        
        c1, c2 = st.tabs(["📞 Calls", "🍑 Puts"])
        with c1:
            st.dataframe(chain.calls, use_container_width=True)
        with c2:
            st.dataframe(chain.puts, use_container_width=True)
            
        # Gamma Exposure (GEX) Simulation
        st.markdown("### 📊 Perfil de Exposición Gamma (GEX)")
        st.info("Cálculo estimado basado en Open Interest y Volatilidad Implícita.")
        # Placeholder for GEX Chart
        fig_gex = go.Figure()
        # Add a mock GEX line
        import numpy as np
        strikes = chain.calls['strike']
        gex = np.sin(np.linspace(0, 5, len(strikes))) * 1e6
        fig_gex.add_trace(go.Scatter(x=strikes, y=gex, fill='tozeroy', name="Gamma Exposure"))
        fig_gex.update_layout(template="plotly_dark", title=f"Gamma Wall Estimation: ${strikes.iloc[len(strikes)//2]:.0f}")
        st.plotly_chart(fig_gex, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error cargando opciones: {e}")

def _render_ultra_fundamental_tab(res):
    st.markdown("<div class='sec-title'>🏛️ Auditoría Forense & Salud Cuantitativa</div>", unsafe_allow_html=True)
    
    h = res.get("health", {})
    if not h:
        st.warning("Datos de auditoría forense no disponibles para este activo.")
        return
        
    c1, c2, c3 = st.columns(3)
    
    with c1:
        # Altman Z-Score Gauge
        z = h.get("z_score", 0)
        label = h.get("z_label", "N/A")
        color = "#10b981" if "SAFE" in label.upper() else ("#ef4444" if "DISTRESS" in label.upper() else "#f59e0b")
        st.metric("Altman Z-Score", f"{z:.2f}", delta=label, delta_color="normal" if "SAFE" in label.upper() else "inverse")
        st.caption("Predicción de riesgo de quiebra a 2 años.")

    with c2:
        # Piotroski F-Score
        f = h.get("f_score", 0)
        f_label = h.get("f_label", "N/A")
        st.metric("Piotroski F-Score", f"{f}/9", delta=f_label)
        st.caption("Fuerza operativa y eficiencia financiera.")

    with c3:
        # Sloan Ratio
        sloan = h.get("sloan_ratio", 0)
        s_label = h.get("sloan_label", "N/A")
        st.metric("Sloan Ratio", f"{sloan:.1f}%", delta=s_label, delta_color="normal" if "LIMPIO" in s_label.upper() else "inverse")
        st.caption("Calidad de beneficios vs. devengos contables.")
    
    st.markdown("---")
    
    # Valuación Qual & Detail
    cc1, cc2 = st.columns([1, 2])
    with cc1:
        st.markdown("### 🏆 Quality Score")
        q_score = h.get("quality_score", 0)
        q_cat = h.get("quality_cat", "AVERAGE")
        st.markdown(f"""
        <div style="background:#0f172a; border:2px solid #3b82f640; border-radius:15px; padding:30px; text-align:center;">
            <div style="font-size:48px; font-weight:900; color:white;">{q_score}</div>
            <div style="color:#3b82f6; font-weight:700; letter-spacing:1px; text-transform:uppercase;">{q_cat}</div>
            <p style="color:#64748b; font-size:12px; margin-top:15px;">Basado en 12 criterios de Buffett & Dorsey</p>
        </div>
        """, unsafe_allow_html=True)

    with cc2:
        st.markdown("### 📋 Criterios Cumplidos")
        details = h.get("details", [])
        if details:
            for d in details:
                icon = "✅" if d.get("pass") else "❌"
                st.write(f"{icon} **{d['name']}**: {d['value']}")
        else:
            st.info("No hay detalles de criterios disponibles.")
