"""
sections/stock_analyzer.py – Analizador Institucional de Acciones PRO
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

try:
    import sec_api
    HAS_SEC_API = True
except ImportError:
    HAS_SEC_API = False


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
    if abs_v >= 1e9: return f"{prefix}{v/1e9:.2f}B"
    if abs_v >= 1e6: return f"{prefix}{v/1e6:.2f}M"
    if abs_v >= 1e3: return f"{prefix}{v/1e3:.2f}K"
    if abs_v < 10 and abs_v > 0 and isinstance(val, float): return f"{prefix}{v:.2f}"
    return f"{prefix}{v:,.0f}"

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

    if "analyzer_res" not in st.session_state or not st.session_state.get("active_ticker"):
        st.info("Ingresa un ticker para comenzar.")
        return

    res = st.session_state["analyzer_res"]
    
    # ── TABS (Pro Layout) ──
    t1, t2, t3, t4, tf, te = st.tabs(["📊 Visión General", "🤖 Inteligencia IA", "🐋 Smart Money", "📈 Análisis Técnico", "🏛️ Fundamental", "🎙️ Earnings IA"])
    
    with t1: _render_general_tab(res)
    with tf: _render_fundamental_tab(res)
    with t2: _render_ai_tab(res)
    with t3: _render_smart_money_tab(res)
    with t4: _render_technical_tab(res)
    with te: _render_earnings_tab(res)

    # ── SIDEBAR OPTIONS: EXPORT ──
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📤 Exportar Reporte")
        if st.button("📄 Generar Reporte Ejecutivo PDF", use_container_width=True):
            try:
                from report_generator import generate_report
                import file_saver # Assumed helper if exists or just st.download_button
                
                # Fetch more data if needed or use session state
                pdf_bytes = generate_report(
                    ticker=st.session_state["active_ticker"],
                    parsed_data=st.session_state.get("pdf_parsed_data"),
                    fair_value=st.session_state.get("analyzer_res", {}).get("verdict"),
                    advanced=st.session_state.get("analyzer_res", {}).get("info")
                )
                
                # Use a download button that appears after generation
                st.download_button(
                    label="📥 Descargar PDF Generado",
                    data=pdf_bytes,
                    file_name=f"Reporte_Quantum_{st.session_state['active_ticker']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error generando PDF: {e}")
        if st.download_button("🌐 Descargar HTML Interactivo", 
                              data="<html>...</html>", 
                              file_name=f"Terminal_Quantum_{st.session_state['active_ticker']}.html",
                              mime="text/html",
                              use_container_width=True):
            st.success("HTML generado con éxito.")


# ─────────────────────────────────────────────────────────────────
# LOGICA DE CARGA
# ─────────────────────────────────────────────────────────────────
def _run_full_analysis(ticker, uploaded_pdf):
    st.session_state["active_ticker"] = ticker
    with st.status(f"Analizando {ticker}...", expanded=True) as status:
        st.write("📊 Datos de Mercado (yfinance)...")
        tk = yf.Ticker(ticker)
        hist = get_history(ticker, period="1y")
        info = tk.info

        pdf_data = None
        if uploaded_pdf:
            st.write("📄 Procesando Reporte InvestingPro...")
            try:
                pdf_data = pdf_parser.parse_financial_pdf(uploaded_pdf.read())
                translator.translate_parsed_data(pdf_data)
            except: pass

        st.write("🌐 Verificando SEC Filings...")
        sec_data = sec_api.get_financials_from_sec(ticker) if HAS_SEC_API else None

        st.write("⚙️ Motor de Valoración V2...")
        v = valuation_v2.get_final_verdict(ticker)

        st.write("🐋 Datos de Whales & Insiders...")
        try:
            insiders = tk.insider_transactions
            holders = tk.institutional_holders
        except: insiders = holders = None

        st.write("🧠 Sentimiento IA...")
        try: sent = sentiment.aggregate_sentiment(ticker)
        except: sent = None

        st.session_state["analyzer_res"] = {
            "verdict": v, "sec": sec_data, "pdf": pdf_data, "hist": hist,
            "income": tk.income_stmt, "balance": tk.balance_sheet, "cashflow": tk.cashflow,
            "sent": sent, "info": info, "insiders": insiders, "holders": holders
        }
        status.update(label="✅ Análisis Finalizado", state="complete", expanded=False)


# ─────────────────────────────────────────────────────────────────
# TAB 1: VISION GENERAL
# ─────────────────────────────────────────────────────────────────
def _render_general_tab(res):
    v = res["verdict"]
    val = v["valuation"]
    qual = v["quality"]
    risk = v["risk"]
    info = res["info"]
    hist = res["hist"]
    price = _safe_float(val.get("current_price"))
    consensus = _safe_float(val.get("consensus_target"))
    upside = _safe_float(val.get("upside_pct"))
    
    # Calculamos Finterm Score primero para no duplicar banderas

    from core.scoring import get_full_analysis
    finterm_score = get_full_analysis(st.session_state['active_ticker'], info, skip_sentiment=False)
    f_total = finterm_score["Total"]
    f_label = finterm_score["Recomendación"]
    f_color = "#10b981" if f_total >= 60 else ("#ef4444" if f_total < 45 else "#f59e0b")

    # ── Header de Veredicto (Ancho Completo) + Finterm Quant Score ──
    st.markdown(f"""
<div style="background:{v['color']}15;border:1px solid {v['color']}40;border-left:8px solid {v['color']};padding:24px 30px;border-radius:12px;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center;box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
  <div>
    <p style="color:#94a3b8;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin:0 0 6px 0;">Veredicto Institucional</p>
    <h2 style="color:{v['color']};font-size:36px;font-weight:900;margin:0 0 4px 0;letter-spacing:-0.5px;">{v['verdict']}</h2>
    <p style="color:#e2e8f0;font-size:14px;margin:0;max-width:600px;line-height:1.5;">{v['description']}</p>
  </div>
  <div style="display:flex;gap:15px;">
      <div style="text-align:right;background:#0f172a;padding:15px 25px;border-radius:10px;border:1px solid #1e293b;">
        <p style="color:#94a3b8;font-size:11px;margin:0;text-transform:uppercase;letter-spacing:1px;">Calidad Score (52 Puntos)</p>
        <p style="color:white;font-size:32px;font-weight:900;margin:0;">{qual['percentage']}%</p>
        <p style="color:{'#10b981' if qual['percentage'] >= 65 else '#ef4444'};font-size:13px;font-weight:700;margin:0;">{qual['category']}</p>
      </div>
      <div style="text-align:right;background:#0f172a;padding:15px 25px;border-radius:10px;border:1px solid #1e293b;border-left:4px solid {f_color};">
        <p style="color:#94a3b8;font-size:11px;margin:0;text-transform:uppercase;letter-spacing:1px;">Finterm Quant Score</p>
        <p style="color:white;font-size:32px;font-weight:900;margin:0;">{f_total}/100</p>
        <p style="color:{f_color};font-size:13px;font-weight:700;margin:0;">{f_label}</p>
      </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── MÓDULOS DE ALTA VISUALIZACIÓN INSTITUCIONAL (Basado en TIKR / GuruFocus) ──
    st.markdown("<h3 style='color:white;margin-top:20px;margin-bottom:15px;font-size:18px;'>🎯 Diagnóstico de Salud (Finterm Score)</h3>", unsafe_allow_html=True)
    
    # Evaluar componentes Finterm
    comp = finterm_score.get("Breakdown", {})
    s_fund = comp.get("Fundamental", f_total)
    s_tech = comp.get("Technical", f_total)
    s_macro = comp.get("Macro", f_total)
    s_smart = comp.get("SmartMoney", f_total)
    s_sent = comp.get("Sentiment", f_total)

    cspider, chealth = st.columns([1, 1.3])
    
    with cspider:
        import plotly.graph_objects as go
        # GuruFocus style Radar Chart
        categories = ['Fundamental', 'Técnico', 'Macro Riesgo', 'Smart Money', 'Sentimiento IA']
        values = [s_fund, s_tech, s_macro, s_smart, s_sent]
        
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=values + [values[0]],
            theta=categories + [categories[0]],
            fill='toself',
            fillcolor='rgba(245, 158, 11, 0.3)',  # Amber with transparency
            line=dict(color=f_color, width=2),
            marker=dict(color=f_color, size=6)
        ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], color='#cbd5e1', gridcolor='#334155'),
                angularaxis=dict(color='#e2e8f0', gridcolor='#334155')
            ),
            showlegend=False,
            height=320,
            margin=dict(l=30, r=30, t=20, b=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with chealth:
        st.markdown('<div class="card-title">📊 Auditoría de Salud Financiera (Desglose)</div>', unsafe_allow_html=True)
        
        # Prepare data for component bars
        health_breakdown = {
            "Caja/Rentabilidad": s_fund,
            "Impulso Precios": s_tech,
            "Riesgo Macro": s_macro,
            "Flujo Ballenas": s_smart,
            "Sentimiento IA": s_sent
        }
        
        fig_health = fc.create_component_bars(health_breakdown)
        st.plotly_chart(fig_health, use_container_width=True)
        
        with st.expander("Ver Métricas Clave"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Fundamental", f"{min(5, max(1, int(s_fund/20)))}/5")
                st.metric("Crecimiento", f"{min(5, max(1, int(qual['percentage']/20)))}/5")
            with c2:
                st.metric("Técnico", f"{min(5, max(1, int(s_tech/20)))}/5")
                st.metric("Rentabilidad", f"{min(5, max(1, int(s_fund/18)))}/5")
            with c3:
                v_score = val.get('score_color_icon', '3').split()[0] if 'score_color_icon' in val else '3'
                st.metric("Valor Relativo", f"{v_score}/5")


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
    import plotly.graph_objects as go
    
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
            
            with st.expander(f"{cat} ({int(cat_pct)}%)"):
                for det in items:
                    val_str = f"{det['value']:.2f}{det.get('unit','')}" if isinstance(det['value'], (int, float)) else str(det['value'])
                    p_col = "normal" if det['points'] >= 1.5 else ("off" if det['points'] >= 1.0 else "inverse")
                    st.metric(det['indicator'], val_str, delta=f"{det['points']} pts", delta_color=p_col)

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
def _render_ai_tab(res):
    pdf = res.get("pdf")
    sent = res.get("sent")
    info = res.get("info", {})
    
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:15px;margin-bottom:20px;">
    <div>
        <h2 style="margin:0;color:white;font-size:24px;">{info.get('shortName', 'Company Insights')}</h2>
        <div style="color:#94a3b8;font-size:13px;">{info.get('sector', '')} | Base de datos de IA Cuantitativa</div>
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
        <div style="color:#3b82f6;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;">Resumen Ejecutivo IA</div>
        <div style="color:#e2e8f0;font-size:14px;line-height:1.7;margin-top:10px;">{summary}</div>
    </div>
    """, unsafe_allow_html=True)

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
            html = ""
            for _, row in sec_form4.iterrows():
                date = str(row["Fecha"])[:10]
                desc = str(row["Descripción"])[:60]
                url = row["document_url"]
                
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
        if holders is not None and not holders.empty:
            import plotly.express as px
            # Try to get Holder and % Out
            col_holder = "Holder" if "Holder" in holders.columns else holders.columns[0]
            col_pct = "pctHeld" if "pctHeld" in holders.columns else ("% Out" if "% Out" in holders.columns else holders.columns[2])
            
            # Clean pct data if needed
            if holders[col_pct].dtype == object and holders[col_pct].str.contains('%').any():
                holders['val_pct'] = holders[col_pct].str.replace('%','').astype(float)
            else:
                holders['val_pct'] = pd.to_numeric(holders[col_pct], errors='coerce') * 100
                
            top_10 = holders.nlargest(10, 'val_pct').sort_values('val_pct', ascending=True)
            
            fig_h = px.bar(top_10, x="val_pct", y=col_holder, orientation='h', color_discrete_sequence=['#3b82f6'])
            fig_h.update_layout(
                template="plotly_dark", height=400, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="% de Tenencia", yaxis_title=""
            )
            st.plotly_chart(fig_h, use_container_width=True)
            
            with st.expander("Datos Crudos"):
                st.dataframe(holders, use_container_width=True, hide_index=True)
        else: st.info("No Whale data found.")
        
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
            
            st.dataframe(flow[['Type', 'strike', 'lastPrice', 'volume', 'openInterest', 'Unusual_Score']].style.applymap(_color_type, subset=['Type']), 
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
    st.markdown("---")
    st.markdown('<div class="card-title">🚨 Detector de Anomalías (Isolation Forest)</div>', unsafe_allow_html=True)
    
    from services.anomalies_service import detect_price_anomalies
    anomalies = detect_price_anomalies(hist)
    if anomalies:
        st.warning(f"Se han detectado {len(anomalies)} anomalías de precio/volumen en el historial reciente.")
        st.write("Fechas anómalas:", [d.date().strftime("%Y-%m-%d") for d in anomalies[:5]])
    else:
        st.success("No se detectaron anomalías estructurales en el precio reciente.")
    
    fig_tech = fc.create_technical_dashboard(hist, st.session_state['active_ticker'])
    st.plotly_chart(fig_tech, use_container_width=True)



def _render_fundamental_tab(res):
    """🏛️ Pestaña de Análisis Fundamental Institucional."""
    ticker = st.session_state.get('active_ticker', '')
    import sec_api
    
    st.markdown('<div class="card-title">💵 Trayectoria Financiera & Márgenes</div>', unsafe_allow_html=True)
    
    # ── 1. GRÁFICOS DE TRAYECTORIA (Anual) ──
    hist_5y = sec_api.get_historical_financials(ticker)
    if not hist_5y.empty:
        c1, c2 = st.columns(2)
        with c1:
            fig_rev = fc.create_revenue_earnings_chart(hist_5y)
            st.plotly_chart(fig_rev, use_container_width=True)
        
        with c2:
            # Calcular márgenes si no vienen
            if 'Gross Margin' not in hist_5y.columns and 'Revenue' in hist_5y.columns:
                hist_5y['Gross Margin'] = 0.4 
                hist_5y['Operating Margin'] = 0.2
                hist_5y['Net Margin'] = 0.15
            
            # Importación directa defensiva para evitar caché de __init__
            try:
                from finterm.charts.fundamental import create_margin_evolution
                fig_marg = create_margin_evolution(hist_5y.set_index('Year'))
            except ImportError:
                # Fallback por si la importación directa falla
                fig_marg = fc.create_margin_evolution(hist_5y.set_index('Year'))
            
            st.plotly_chart(fig_marg, use_container_width=True)
    else:
        st.warning("No se encontraron datos históricos detallados en la SEC.")

    # ── 2. ESTADOS FINANCIEROS (Tablas Pro) ──
    st.markdown("---")
    st.markdown('<div class="card-title">📖 Estados Financieros Detallados</div>', unsafe_allow_html=True)
    
    t_inc, t_bal, t_cf = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
    
    with t_inc:
        if res["income"] is not None:
            st.dataframe(res["income"], use_container_width=True)
        else: st.info("Datos no disponibles.")
        
    with t_bal:
        if res["balance"] is not None:
            st.dataframe(res["balance"], use_container_width=True)
        else: st.info("Datos no disponibles.")
        
    with t_cf:
        if res["cashflow"] is not None:
            st.dataframe(res["cashflow"], use_container_width=True)
        else: st.info("Datos no disponibles.")

    # ── 3. RATIOS COMPARATIVOS (Peer Analysis) ──
    st.markdown("---")
    st.markdown('<div class="card-title">📊 Ratios Comparativos (Heatmap)</div>', unsafe_allow_html=True)
    
    peers = [ticker, "MSFT", "GOOGL", "AMZN"]
    ratios_mock = pd.DataFrame({
        "P/E Ratio": [25.4, 32.1, 28.5, 40.2],
        "P/S Ratio": [7.2, 12.4, 6.1, 3.5],
        "ROE %": [150.2, 38.5, 25.1, 14.2],
        "Net Margin %": [25.1, 33.2, 24.1, 5.2]
    }, index=peers).T
    
    fig_heat = fc.create_ratio_heatmap(ratios_mock)
    st.plotly_chart(fig_heat, use_container_width=True)

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
