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
from cache_utils import get_history
import pdf_parser
import translator
import valuation_v2
import sentiment
from ui_shared import fmt
from utils.visual_components import inject_custom_css

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
    t1, t2, t3, t4 = st.tabs(["🏠 Visión General", "🧠 Inteligencia IA", "🐋 Smart Money", "📈 Análisis Técnico"])
    
    with t1: _render_general_tab(res)
    with t2: _render_ai_tab(res)
    with t3: _render_smart_money_tab(res)
    with t4: _render_technical_tab(res)


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
    
    # Verdict Banner
    st.markdown(f"""
    <div style="background:{v['color']}18;border-left:6px solid {v['color']};padding:16px 22px;border-radius:8px;margin-bottom:22px;display:flex;justify-content:space-between;">
      <div>
        <p style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0;">Veredicto Institucional</p>
        <h2 style="color:{v['color']};font-size:28px;font-weight:800;margin:4px 0 2px;">{v['verdict']}</h2>
        <p style="color:#cbd5e1;font-size:13px;margin:0;">{v['description']}</p>
      </div>
      <div style="text-align:right;">
        <p style="color:#94a3b8;font-size:11px;margin:0;">Calidad Score</p>
        <p style="color:white;font-size:24px;font-weight:800;margin:0;">{qual['percentage']}%</p>
        <p style="color:#64748b;font-size:11px;">{qual['category']}</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    cl, cr = st.columns([1.6, 1], gap="large")
    
    low_s = _get_clean_series(hist, "Low")
    high_s = _get_clean_series(hist, "High")
    lo52 = _safe_float(low_s.min()) if low_s is not None else 0.0
    hi52 = _safe_float(high_s.max()) if high_s is not None else 0.0

    with cl:
        # Header Info
        day_chg = _safe_float(info.get("regularMarketChange"))
        day_pct = _safe_float(info.get("regularMarketChangePercent"))
        chg_col = "#10b981" if day_chg >= 0 else "#ef4444"
        
        st.markdown(f"""
        <div style="margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;align-items:baseline;">
                <span style="font-size:32px;font-weight:900;color:white;">{st.session_state['active_ticker']} <span style="font-size:14px;color:#64748b;">{info.get('exchange','')}</span></span>
                <span style="font-size:28px;font-weight:800;color:white;">${price:.2f} <span style="font-size:14px;color:{chg_col};">${day_chg:+.2f} ({day_pct:+.2f}%)</span></span>
            </div>
            <div style="color:#64748b;font-size:12px;">{info.get('longName','')} · {info.get('industry','')}</div>
        </div>
        """, unsafe_allow_html=True)

        row1 = st.columns(3)
        row1[0].markdown(_info_card("Sector", info.get("sector","—")), unsafe_allow_html=True)
        row1[1].markdown(_info_card("MOAT (IA)", qual.get("moat","—")), unsafe_allow_html=True)
        with row1[2]:
            st.markdown(f'<div class="card-title">52W Range</div><div style="color:white;font-size:14px;font-weight:700;">${lo52:.2f} - ${hi52:.2f}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#64748b;font-size:10px;margin-top:4px;">{_market_badge(info.get("marketState"))}</div>', unsafe_allow_html=True)

        # Radar Chart: Scatterpolar
        import plotly.graph_objects as go
        st.markdown('<div class="card-title">📐 Salud Financiera (Radar)</div>', unsafe_allow_html=True)
        # Using Scatterpolar with fill to resemble a true spider chart
        theta = list(qual["radar_data"].keys())
        r = list(qual["radar_data"].values())
        # Close the loop
        theta.append(theta[0])
        r.append(r[0])
        
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatterpolar(
            r=r, theta=theta, fill='toself',
            fillcolor='rgba(59,130,246,0.3)', line_color='#3b82f6',
            marker=dict(size=8, color='#10b981')
        ))
        
        # Clean tick text (remove strange encoded prefixes like 'â-,')
        clean_theta = [t.split(" ", 1)[1] if " " in t else t for t in theta[:-1]]
        
        fig_r.update_layout(
            template="plotly_dark", 
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], gridcolor='#334155', tickfont=dict(color='#94a3b8')),
                angularaxis=dict(gridcolor='#334155', tickvals=list(range(len(clean_theta))), ticktext=clean_theta)
            ),
            showlegend=False, margin=dict(l=40, r=40, t=30, b=30), height=350,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_r, use_container_width=True)

        st.markdown("---")
        st.markdown('<div class="card-title">🔍 Auditoría de 52 Puntos</div>', unsafe_allow_html=True)
        for cat, items in qual["categorized_details"].items():
            clean_cat = cat.split(" ", 1)[1] if " " in cat else cat # Fix encoding artifact before emoji
            with st.expander(f"{clean_cat}", expanded=False):
                for det in items:
                    c1, c2, c3, c4 = st.columns([3, 1, 0.5, 1.5])
                    c1.markdown(f"<span style='color:#e2e8f0;font-size:12px;'>{det['indicator']}</span>", unsafe_allow_html=True)
                    val_str = f"{det['value']:.2f}{det.get('unit','')}" if isinstance(det['value'], (int, float)) else str(det['value'])
                    c2.markdown(f"<span style='color:white;font-weight:700;'>{val_str}</span>", unsafe_allow_html=True)
                    c3.markdown(f"<span style='color:{'#10b981' if det['points']>=1.5 else '#f59e0b'};font-weight:700;'>{det['points']}</span>", unsafe_allow_html=True)
                    c4.markdown(_progress_bar_html(det["points"]), unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="card-title">⌛ Tendencias de 5 Años</div>', unsafe_allow_html=True)
        hist_5y = sec_api.get_historical_financials(st.session_state['active_ticker'])
        if not hist_5y.empty:
            fig_h = go.Figure()
            fig_h.add_trace(go.Scatter(x=hist_5y["Year"], y=hist_5y["Revenue"], name="Ingresos", fill='tozeroy', line_color="#3b82f6"))
            fig_h.add_trace(go.Scatter(x=hist_5y["Year"], y=hist_5y["Net Income"], name="Beneficio", fill='tozeroy', line_color="#10b981"))
            fig_h.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=20, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig_h, use_container_width=True)
        else:
            st.info("Datos históricos limitados para este ticker.")

        st.markdown("---")
        def _render_fin_table(title, df, emoji):
            if df is None or df.empty: return
            with st.expander(f"{emoji} {title}", expanded=True):
                disp_df = df.head(6).applymap(lambda x: _fmt_val(x) if isinstance(x, (int, float)) else x)
                # Clean up index titles which sometimes contain weird chars
                disp_df.index = [str(idx).encode("ascii", "ignore").decode() for idx in disp_df.index]
                st.dataframe(disp_df, use_container_width=True)

        _render_fin_table("Cuenta de Resultados", res["income"], "📊")
        _render_fin_table("Balance General", res["balance"], "⚖️")
        _render_fin_table("Flujo de Efectivo", res["cashflow"], "💸")

    with cr:
        # Fair Value Sliders
        st.markdown('<div class="stCard">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Valor Razonable</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;margin:10px 0;">
            <div style="text-align:center;"><div style="color:#64748b;font-size:10px;">CONSENSO</div><div style="color:{'#10b981' if upside>0 else '#ef4444'};font-size:20px;font-weight:800;">${consensus:.2f}</div></div>
            <div style="text-align:center;"><div style="color:#64748b;font-size:10px;">UPSIDE</div><div style="color:{'#10b981' if upside>0 else '#ef4444'};font-size:20px;font-weight:800;">{upside:+.1f}%</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Breakdown Table
        st.markdown('<div style="color:#94a3b8;font-size:11px;margin-bottom:8px;">DESGLOSE DE MODELOS</div>', unsafe_allow_html=True)
        models = [
            ("DCF Institucional", val['dcf_institucional']),
            ("DCF Simple", val['dcf_simple']),
            ("Peter Lynch (PEG)", val['lynch_peg']),
            ("Relativo (Múltiplos)", val['multiples']),
            ("Monte Carlo (P50)", val['montecarlo_p50'])
        ]
        for name, value in models:
            m_col1, m_col2 = st.columns([2, 1])
            m_col1.markdown(f"<span style='color:#cbd5e1;font-size:12px;'>{name}</span>", unsafe_allow_html=True)
            diff = value - price
            pct = (diff / price * 100) if price else 0
            color = "#10b981" if pct >= 0 else "#ef4444"
            m_col2.markdown(f"<div style='text-align:right;'><span style='color:white;font-weight:700;font-size:12px;'>${value:.2f}</span> <span style='color:{color};font-size:10px;'>{pct:+.1f}%</span></div>", unsafe_allow_html=True)
            st.markdown("<div style='height:1px;background:#1e293b;margin:2px 0;'></div>", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:15px;'>", unsafe_allow_html=True)
        l_min = _safe_float(low_s.min()) if low_s is not None else 0.0
        h_max = _safe_float(high_s.max()) if high_s is not None else 0.0
        
        st.markdown(_range_bar_html("Precio vs 52W", "", price, l_min, h_max, "#3b82f6"), unsafe_allow_html=True)
        st.markdown(_range_bar_html("Consenso Analyst", "", val.get("analyst_mean",0), val.get("analyst_low",0), val.get("analyst_high",0), "#f59e0b"), unsafe_allow_html=True)
        st.markdown(_range_bar_html("Modelos Quantum", "", consensus, min([val['dcf_institucional'], val['dcf_simple']]), max([val['dcf_institucional'], val['dcf_simple']]), "#10b981"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Auditores
        st.markdown(f"""
        <div class="stCard">
          <div class="card-title">Auditores de Riesgo (Bloque C)</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;">
            <div style="background:#0f172a;padding:8px;border-radius:6px;text-align:center;">
              <div style="color:#64748b;font-size:9px;">ALTMAN Z</div>
              <div style="color:{'#10b981' if 'SAFE' in risk['altman_label'] else '#ef4444'};font-size:18px;font-weight:800;">{risk['altman_z']}</div>
            </div>
            <div style="background:#0f172a;padding:8px;border-radius:6px;text-align:center;">
              <div style="color:#64748b;font-size:9px;">SLOAN %</div>
              <div style="color:{'#10b981' if 'LIMPIO' in risk['sloan_label'] else '#ef4444'};font-size:18px;font-weight:800;">{risk['sloan_ratio']}%</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)


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
            st.markdown('<div class="card-title">Barómetro de Sentimiento General</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="display:flex;height:12px;border-radius:6px;overflow:hidden;margin-bottom:25px;">
                <div style="width:{(bull/total)*100}%;background:#10b981;" title="Bullish {bull}"></div>
                <div style="width:{(neut/total)*100}%;background:#64748b;" title="Neutral {neut}"></div>
                <div style="width:{(bear/total)*100}%;background:#ef4444;" title="Bearish {bear}"></div>
            </div>
            """, unsafe_allow_html=True)

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
    
    st.markdown(f"""
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
    """, unsafe_allow_html=True)

    tab_i, tab_h = st.tabs(["🕵️ Transacciones Insiders", "🏦 Top Holders Institucionales"])
    
    with tab_i:
        if insiders is not None and not insiders.empty:
            preferred = ['Insider', 'Position', 'Transaction', 'Start Date', 'Shares', 'Value', 'Relation', 'Date']
            clean_df = _safe_df_cols(insiders, preferred)
            # Render visually instead of raw table
            html = ""
            for _, row in clean_df.head(10).iterrows():
                actor = row.get("Insider") or row.get("Relation") or "Desconocido"
                date = str(row.get("Date") or row.get("Start Date") or "-")[:10]
                action = str(row.get("Transaction") or "Unknown").lower()
                shares = _safe_float(row.get("Shares", 0))
               
                is_buy = "buy" in action or "purchase" in action
                color = "#10b981" if is_buy else ("#ef4444" if "sale" in action or "sell" in action else "#f59e0b")
                action_text = "COMPRA" if is_buy else ("VENTA" if "sale" in action or "sell" in action else "OTRO")
                
                html += f"""
                <div style="display:flex;justify-content:space-between;align-items:center;background:#0a0f1a;padding:12px 18px;border-left:4px solid {color};margin-bottom:8px;border-radius:6px;">
                    <div>
                        <div style="color:white;font-weight:700;font-size:14px;">{actor}</div>
                        <div style="color:#64748b;font-size:11px;">{date}</div>
                    </div>
                    <div style="text-align:right;">
                        <span style="background:{color}20;color:{color};padding:2px 8px;border-radius:12px;font-size:10px;font-weight:800;margin-right:10px;">{action_text}</span>
                        <span style="color:white;font-weight:600;">{_fmt_val(shares, '')} Acciones</span>
                    </div>
                </div>
                """
            st.markdown(html, unsafe_allow_html=True)
            if len(clean_df) > 10:
                with st.expander("Ver todas las transacciones"):
                    st.dataframe(clean_df, use_container_width=True, hide_index=True)
        else: st.info("No Insider data found.")
            
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

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.2, 0.15])
    
    # 1. Price & MAs
    fig.add_trace(go.Candlestick(x=hist.index, open=open_p, high=high, low=low, close=close, name="Precio", increasing_line_color='#10b981', decreasing_line_color='#ef4444'), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=sma20, name="SMA 20", line=dict(color='#f59e0b', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=sma50, name="SMA 50", line=dict(color='#3b82f6', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=bb_upper, name="BB Upper", line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=bb_lower, name="BB Lower", line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(255,255,255,0.03)'), row=1, col=1)
    
    # 2. Volume
    fig.add_trace(go.Bar(x=hist.index, y=volume, name="Volumen", marker_color=vol_colors, opacity=0.8), row=2, col=1)
    
    # 3. MACD
    fig.add_trace(go.Bar(x=hist.index, y=macd_hist, name="MACD Hist", marker_color=macd_colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=macd, name="MACD", line=dict(color='#3b82f6', width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=sig, name="Signal", line=dict(color='#f59e0b', width=1)), row=3, col=1)
    
    # 4. RSI
    fig.add_trace(go.Scatter(x=hist.index, y=rsi, name="RSI", line=dict(color='#a855f7', width=1.5)), row=4, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", row=4, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#10b981", row=4, col=1)
    
    fig.update_layout(
        height=800, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # Timeframe Selector
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=3, label="3M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1A", step="year", stepmode="backward"),
                dict(step="all", label="TODO")
            ]),
            bgcolor="#1e293b", activecolor="#3b82f6", font=dict(color="white")
        ),
        row=1, col=1
    )
    
    st.plotly_chart(fig, use_container_width=True)
