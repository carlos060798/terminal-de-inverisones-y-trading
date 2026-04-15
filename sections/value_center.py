"""
sections/value_center.py - Fundamental Value Center
Consolidates Intrinsic Value, Peter Lynch, Financial Health, and Dividend Analysis.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import yfinance as yf
import database as db
import valuation
from ui_shared import DARK, dark_layout, fmt, kpi

def _sec(title):
    st.markdown(f"<div class='sec-title'>{title}</div>", unsafe_allow_html=True)

def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Centro de Valor Fundamental</h1>
        <p>Valuación Intrínseca · Peter Lynch · Salud Financiera · Dividendos</p>
      </div>
    </div>""", unsafe_allow_html=True)

    ticker = st.session_state.get("active_ticker", "").strip().upper()
    if not ticker:
        st.info("Inserta un Ticker en la barra superior para comenzar el análisis fundamental.")
        return

    # Load Data
    with st.spinner(f"Analizando {ticker}..."):
        try:
            tk = yf.Ticker(ticker)
            info = tk.info
            if not info or 'symbol' not in info:
                st.error(f"No se encontraron datos para {ticker}. Verifica el símbolo.")
                return
        except Exception as e:
            st.error(f"Error cargando yfinance: {e}")
            return

    # Tabs
    tab_val, tab_lynch, tab_health, tab_dupont, tab_div, tab_13f, tab_magic = st.tabs([
        "💎 Valuación", "🎩 Peter Lynch", "🏥 Salud & Calidad", "🧪 DuPont", "💰 Dividendos", "🐋 13F Smart Money", "🏆 Magic Formula"
    ])

    # ── TAB 1: VALUACIÓN ──────────────────────────────────────────────────────
    with tab_val:
        _render_valuation_tab(ticker, info)

    # ── TAB 2: PETER LYNCH ────────────────────────────────────────────────────
    with tab_lynch:
        _render_lynch_tab(ticker, info)

    # ── TAB 3: SALUD & CALIDAD ────────────────────────────────────────────────
    with tab_health:
        _render_health_tab(ticker, info)

    # ── TAB 4: DUPONT ─────────────────────────────────────────────────────────
    with tab_dupont:
        _render_dupont_tab(ticker, info)

    # ── TAB 5: DIVIDENDOS ─────────────────────────────────────────────────────
    with tab_div:
        _render_dividend_tab(ticker, info)

    # ── TAB 6: SMART MONEY ────────────────────────────────────────────────────
    with tab_13f:
        _render_13f_tab(ticker, info)

    # ── TAB 7: MAGIC FORMULA ──────────────────────────────────────────────────
    with tab_magic:
        _render_magic_tab()

def _render_valuation_tab(ticker, info):
    _sec("Dashboard de Valor Intrínseco")
    
    # Intrinsic Value Triangulation
    fv_data = valuation.compute_fair_values(ticker)
    
    c1, c2, c3, c4 = st.columns(4)
    price = fv_data.get("current_price", 0)
    avg_fv = fv_data.get("avg_fair_value", 0)
    upside = fv_data.get("upside_pct", 0)
    
    c1.markdown(kpi("Precio Actual", fmt(price), "", "blue"), unsafe_allow_html=True)
    c2.markdown(kpi("Fair Value (Promedio)", fmt(avg_fv, prefix="$"), "", "purple"), unsafe_allow_html=True)
    
    upside_val = upside if upside is not None else 0
    color = "green" if upside_val > 0 else "red"
    c3.markdown(kpi("Upside Potencial", fmt(upside, prefix="%"), "", color), unsafe_allow_html=True)
    
    signal = fv_data.get("signal", "N/A").upper()
    sig_col = fv_data.get("signal_color", "blue")
    c4.markdown(kpi("Veredicto", signal, "vs. Avg Fair Value", sig_col), unsafe_allow_html=True)

    # ── Barbell Chart (Margin of Safety) ──
    st.markdown("<br>", unsafe_allow_html=True)
    _sec("📉 Visualización: Barbell de Margen de Seguridad")
    
    # Extract method values
    pe_val = fv_data.get("pe_fair_value", 0)
    dcf_val = fv_data.get("dcf_fair_value", 0)
    peg_val = fv_data.get("peg_fair_value", 0)
    low_v = min(filter(None, [pe_val, dcf_val, peg_val]), default=0)
    high_v = max(filter(None, [pe_val, dcf_val, peg_val]), default=0)
    
    fig_barbell = go.Figure()
    # Range line
    fig_barbell.add_trace(go.Scatter(x=[low_v, high_v], y=[0, 0], mode="lines+markers", 
                                     line=dict(color="#475569", width=6), marker=dict(size=12, color="#60a5fa"),
                                     name="Rango Fair Value"))
    # Current Price marker
    price_color = "#10b981" if price < avg_fv else "#ef4444"
    fig_barbell.add_trace(go.Scatter(x=[price], y=[0], mode="markers+text", 
                                     text=[f"PRECIO: ${price:,.2f}"], textposition="top center",
                                     marker=dict(color=price_color, size=20, symbol="diamond", line=dict(width=2, color="white")),
                                     name="Precio Actual"))
    
    # Annotations for Low/High
    fig_barbell.add_annotation(x=low_v, y=-0.05, text="MÍN (PESIMISTA)", showarrow=False, font=dict(size=10, color="#94a3b8"))
    fig_barbell.add_annotation(x=high_v, y=-0.05, text="MÁX (OPTIMISTA)", showarrow=False, font=dict(size=10, color="#94a3b8"))
    fig_barbell.add_annotation(x=avg_fv, y=0.08, text=f"PROMEDIO: ${avg_fv:,.2f}", showarrow=True, arrowhead=2, font=dict(color="#a78bfa"))

    fig_barbell.update_layout(
        **dark_layout(height=280, showlegend=False),
        xaxis=dict(showgrid=True, gridcolor="#1a1a1a", zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, range=[-0.15, 0.2])
    )
    st.plotly_chart(fig_barbell, use_container_width=True, config={'displayModeBar': False})

    # Methodology breakdown
    st.markdown("---")
    
    # ── AI VALUATION INSIGHT ──
    if st.button("🤖 Generar Análisis de Valor IA", use_container_width=True):
        from services.text_service import analyze_stock
        with st.spinner("Modelos de IA analizando fundamentos..."):
            res_ai, provider = analyze_stock(
                ticker, 
                price=price, 
                pe=fv_data.get("pe_method", {}).get("applied_pe", 0),
                fair_value=avg_fv
            )
            if res_ai:
                st.session_state["val_ai_cache"] = res_ai
                st.session_state["val_ai_provider"] = provider
                
    if "val_ai_cache" in st.session_state:
        prov_lbl = st.session_state.get("val_ai_provider", "IA")
        st.markdown(f"""
        <div style="background:rgba(139, 92, 246, 0.05); border:1px solid rgba(139, 92, 246, 0.2); padding:20px; border-radius:12px; margin-bottom:20px;">
            <div style="color:#8b5cf6; font-size:12px; font-weight:800; text-transform:uppercase; margin-bottom:10px;">🤖 Quantum AI Valuator ({prov_lbl})</div>
            <div style="color:#e2e8f0; font-size:13px; line-height:1.6;">{st.session_state["val_ai_cache"]}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    
    # Method boxes with improved design
    def _meth_box(title, val, details, color_hex):
        st.markdown(f"""
        <div style='background:rgba(30,41,59,0.3); backdrop-filter:blur(10px); border:1px solid rgba(255,255,255,0.05); border-top: 3px solid {color_hex}; border-radius:12px; padding:20px; margin-bottom:10px;'>
            <div style='font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px;'>{title}</div>
            <div style='font-size:24px; font-weight:800; color:{color_hex};'>{fmt(val)}</div>
            <div style='font-size:11px; color:#94a3b8; margin-top:5px;'>{details}</div>
        </div>
        """, unsafe_allow_html=True)

    with m1:
        pe_fv = fv_data.get("pe_fair_value")
        det = fv_data.get("details", {}).get("pe_method", {})
        _meth_box("Basado en Múltiplos P/E", pe_fv if pe_fv else 0, f"Sector P/E: {det.get('applied_pe',0):.1f}x", "#60a5fa")
    
    with m2:
        dcf_fv = fv_data.get("dcf_fair_value")
        det = fv_data.get("details", {}).get("dcf_method", {})
        _meth_box("DCF (Simple)", dcf_fv if dcf_fv else 0, f"G: {det.get('growth_rate',0)*100:.1f}% | R: {det.get('discount_rate',0)*100:.1f}%", "#a78bfa")
        
    with m3:
        peg_fv = fv_data.get("peg_fair_value")
        det = fv_data.get("details", {}).get("peg_method", {})
        _meth_box("Peter Lynch (PEG=1)", peg_fv if peg_fv else 0, f"Growth: {det.get('earnings_growth',0)*100:.1f}%", "#34d399")

    # WACC & Sensitivity
    st.markdown("### Matriz de Sensibilidad WACC vs Terminal G")
    wacc_pro = valuation.compute_dcf_professional(ticker)
    if wacc_pro and "sensitivity" in wacc_pro:
        sens = wacc_pro["sensitivity"]
        w_range = wacc_pro["wacc_range"]
        g_range = wacc_pro["g_range"]
        
        # Build matrix
        matrix_data = []
        for w in w_range:
            row = []
            for g in g_range:
                val = sens.get((round(w*100, 2), round(g*100, 2)), 0)
                row.append(val)
            matrix_data.append(row)
            
        fig_sens = go.Figure(data=go.Heatmap(
            z=matrix_data,
            x=[f"g: {g*100:.1f}%" for g in g_range],
            y=[f"WACC: {w*100:.2f}%" for w in w_range],
            colorscale='Blues',
            text=matrix_data,
            texttemplate="%{text}",
            showscale=False
        ))
        fig_sens.update_layout(**dark_layout(height=400, margin=dict(l=40, r=40, t=20, b=40)))
        st.plotly_chart(fig_sens, use_container_width=True)
        st.caption("Esta matriz muestra cómo varía el valor justo (DCF) ante cambios en el coste de capital y el crecimiento perpetuo.")

    st.markdown("---")
    _sec("⚡ Stress Test: Impacto de Tasas (WACC)")
    with st.expander("Simular cambios en el entorno de tasas", expanded=True):
        base_wacc = wacc_pro.get("wacc", 0.10)
        adj_wacc = st.slider("Ajuste de Tasa / WACC (bps)", -300, 500, 0, step=50, help="Simula cambios en la tasa libre de riesgo o prima de riesgo.")
        
        new_wacc_val = base_wacc + (adj_wacc / 10000)
        st.write(f"WACC Base: **{base_wacc*100:.2f}%** → WACC Simulado: **{new_wacc_val*100:.2f}%**")
        
        # Recalculate DCF with new WACC
        new_dcf_res = valuation.compute_dcf_professional(ticker, wacc_override=new_wacc_val)
        new_fv_val = new_dcf_res.get("fair_value_per_share", 0)
        old_fv_val = wacc_pro.get("fair_value_per_share", 0)
        
        str1, str2 = st.columns(2)
        str1.markdown(kpi("Fair Value Original", f"${old_fv_val:.2f}", f"WACC {base_wacc*100:.1f}%", "blue"), unsafe_allow_html=True)
        
        if old_fv_val > 0:
            diff_pct = ((new_fv_val - old_fv_val) / old_fv_val) * 100
            diff_col = "purple" if diff_pct > 0 else "red"
            str2.markdown(kpi("Fair Value Simulado", f"${new_fv_val:.2f}", f"Impacto: {diff_pct:+.1f}%", diff_col), unsafe_allow_html=True)

    st.markdown("---")
    _sec("🕵️ Análisis de Valuación Inversa (Reverse DCF)")
    
    implied_g = valuation.solve_implied_growth(ticker)
    est_g = (info.get("earningsGrowth", 0) or 0) * 100
    hist_g = (info.get("revenueGrowth", 0) or 0) * 100
    
    vi1, vi2 = st.columns([1, 2])
    with vi1:
        st.markdown(f"""
        <div class='metric-card' style='background:rgba(251,191,36,0.05); border:1px solid rgba(251,191,36,0.3);'>
            <div class='mc-label'>Crecimiento Implícito (Market)</div>
            <div class='mc-value' style='color:#fbbf24;'>{implied_g if implied_g is not None else 'N/A'}%</div>
            <div class='mc-bench'>Crecimiento anual necesario para justificar ${price}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if implied_g and est_g:
            gap = est_g - implied_g
            gap_col = "#34d399" if gap > 0 else "#f87171"
            st.markdown(f"<div style='text-align:center; margin-top:10px; color:{gap_col}; font-weight:700;'>Gap vs. Estimados: {gap:+.1f}%</div>", unsafe_allow_html=True)

    with vi2:
        # Comparison chart
        comp_data = pd.DataFrame({
            "Tipo": ["Implícito (Mkt)", "Estimado (Analistas)", "Histórico (Rev)"],
            "Crecimiento %": [implied_g or 0, est_g, hist_g]
        })
        fig_implied = px.bar(comp_data, x="Tipo", y="Crecimiento %", color="Tipo",
                             color_discrete_map={"Implícito (Mkt)": "#fbbf24", "Estimado (Analistas)": "#60a5fa", "Histórico (Rev)": "#94a3b8"})
        fig_implied.update_layout(**dark_layout(height=300, showlegend=False))
        st.plotly_chart(fig_implied, use_container_width=True)

def _render_lynch_tab(ticker, info):
    _sec("Sistema de Inversión Peter Lynch")
    
    # Classification logic
    rev_growth = info.get("revenueGrowth", 0) or 0
    earn_growth = info.get("earningsGrowth", 0) or 0
    pe = info.get("trailingPE") or info.get("forwardPE") or 0
    div = info.get("dividendYield", 0) or 0
    mkt_cap = info.get("marketCap", 0) or 0
    
    category = "Desconocida"
    desc = ""
    
    if rev_growth > 0.20:
        category = "Fast Grower"
        desc = "Empresa de alto crecimiento indomable. Potencial 'Multi-bagger'."
    elif 0.10 <= rev_growth <= 0.15:
        category = "Stalwart"
        desc = "Empresa sólida, crecimiento estable. Defensa en recesiones."
    elif rev_growth < 0.05 and div > 0.03:
        category = "Slow Grower"
        desc = "Crecimiento lento pero generosa en dividendos."
    elif mkt_cap > 5e11: # Meta/Google etc
        category = "Asset Play / Stalwart"
        desc = "Gigante con activos masivos o monopolio de mercado."
    else:
        category = "Cyclical / Other"
        desc = "Su evolución depende fuertemente del ciclo económico."

    cl1, cl2 = st.columns([1, 2])
    with cl1:
        st.markdown(f"""
        <div style='background:rgba(96,165,250,0.1); border:1px solid #60a5fa; border-radius:14px; padding:24px; text-align:center;'>
            <div style='color:#60a5fa; font-size:11px; text-transform:uppercase; letter-spacing:2px; font-weight:700;'>CATEGORÍA LYNCH</div>
            <div style='color:#f0f6ff; font-size:32px; font-weight:800; margin:10px 0;'>{category}</div>
            <div style='color:#94a3b8; font-size:14px;'>{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Lynch check: P/E vs G+Y
        total_ret = (earn_growth + div) * 100
        lynch_ratio = total_ret / pe if pe > 0 else 0
        l_color = "#34d399" if lynch_ratio >= 1.5 else ("#fbbf24" if lynch_ratio >= 1.0 else "#f87171")
        
        st.markdown(f"""
        <div class='metric-card' style='margin-top:20px;'>
            <div class='mc-label'>Ratio Lynch (G+Y)/PE</div>
            <div class='mc-value' style='color:{l_color};'>{lynch_ratio:.2f}</div>
            <div class='mc-bench'>> 1.5 es ideal | Actual: {total_ret:.1f}% / {pe:.1f}x</div>
        </div>
        """, unsafe_allow_html=True)

    with cl2:
        # The Lynch Chart (Price vs Earnings Line)
        try:
            hist = tk.history(period="10y")
            if not hist.empty:
                prices = hist['Close']
                # Get EPS history (simplified)
                # For real Lynch chart, we'd need annual EPS. We'll proxy with a linear scale if missing.
                eps = info.get("trailingEps", 0)
                lynch_line = eps * 15
                
                fig_lynch = go.Figure()
                fig_lynch.add_trace(go.Scatter(x=prices.index, y=prices.values, name="Precio", line=dict(color="#60a5fa", width=2)))
                # Proxy historical lynch line (using current EPS as static for now, or real if we had it)
                fig_lynch.add_hline(y=lynch_line, line_dash="dash", line_color="#fbbf24", annotation_text="Lynch Line ($15x EPS)")
                
                fig_lynch.update_layout(**dark_layout(height=350, title=dict(text=f"Lynch Chart: {ticker}", font=dict(size=14, color="#94a3b8"))))
                st.plotly_chart(fig_lynch, use_container_width=True)
                st.caption("La 'Lynch Line' (EPS x 15) es una regla empírica: si el precio está muy por debajo de la línea, la acción suele estar infravalorada.")
        except:
            st.info("No se pudo generar el Lynch Chart detallado.")

def _render_health_tab(ticker, info):
    _sec("Salud Financiera & Calidad")
    
    h_data = valuation.compute_health_scores(ticker)
    q_data = valuation.compute_fundamental_score_v2(ticker)
    
    r1, r2 = st.columns(2)
    
    with r1:
        st.markdown("#### Altman Z-Score (Probabilidad de Quiebra)")
        z = h_data.get("z_score", 0)
        z_label = h_data.get("z_label", "N/A")
        z_colors = {"SAFE": "#34d399", "GREY": "#fbbf24", "DISTRESS": "#f87171", "N/A": "#475569"}
        z_col = z_colors.get(z_label, "#475569")
        
        fig_z = go.Figure(go.Indicator(
            mode="gauge+number",
            value=z,
            number={"font": {"color": z_col}},
            gauge={
                "axis": {"range": [0, 5]},
                "bar": {"color": z_col},
                "steps": [
                    {"range": [0, 1.8], "color": "rgba(248,113,113,0.1)"},
                    {"range": [1.8, 3], "color": "rgba(251,191,36,0.1)"},
                    {"range": [3, 5], "color": "rgba(52,211,153,0.1)"}
                ]
            }
        ))
        fig_z.update_layout(**dark_layout(height=250))
        st.plotly_chart(fig_z, use_container_width=True)
        st.markdown(f"<div style='text-align:center; color:{z_col}; font-weight:700;'>ESTADO: {z_label}</div>", unsafe_allow_html=True)

    with r2:
        st.markdown("#### Piotroski F-Score (Robustez Operativa)")
        f = h_data.get("f_score", 0)
        f_label = h_data.get("f_label", "N/A")
        
        st.markdown(f"""
        <div style='text-align:center; padding:40px 0;'>
            <div style='font-size:72px; font-weight:800; color:#60a5fa;'>{f}<span style='font-size:24px; color:#475569;'>/9</span></div>
            <div style='font-size:18px; font-weight:600; color:#94a3b8;'>VALORACIÓN: {f_label}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("Ver criterios de rentabilidad (Piotroski)"):
            for crit, ok in h_data.get("f_details", {}).items():
                st.write(f"{'✅' if ok else '❌'} {crit}")

    st.markdown("---")
    _sec("Calidad de Ganancias (Sloan Ratio)")
    sl_val = h_data.get("sloan_ratio")
    sl_lab = h_data.get("sloan_label", "N/A")
    sl_col = "#34d399" if sl_lab == "SAFE" else "#f87171"
    
    sc1, sc2 = st.columns([1, 2])
    sc1.markdown(kpi("Sloan Ratio", f"{sl_val:.4f}" if sl_val else "N/A", sl_lab, sl_col), unsafe_allow_html=True)
    sc2.info("El Sloan Ratio ayuda a detectar si los beneficios están respaldados por caja real. Un ratio fuera del rango [-0.10, 0.10] sugiere un exceso de devengos (accruals) que podría indicar manipulación contable.")

    st.markdown("---")
    _sec("Calidad Institucional (Buffett/Dorsey Score)")
    
    score = q_data.get("percentage", 0)
    cat = q_data.get("category", "N/A")
    sc_col = "#34d399" if score >= 80 else ("#fbbf24" if score >= 60 else "#f87171")
    
    st.markdown(f"""
    <div style='display:flex; justify-content:space-between; align-items:center; background:#0a0a0a; border: 1px solid #1a1a1a; padding: 20px; border-radius: 14px;'>
        <div>
            <div style='color:#5a6f8a; font-size:12px; font-weight:600; text-transform:uppercase;'>Puntuación de Calidad V2</div>
            <div style='color:#f0f6ff; font-size:28px; font-weight:800;'>{score:.1f}%</div>
        </div>
        <div style='background:{sc_col}; color:#000; padding:8px 16px; border-radius:8px; font-weight:700;'>
            {cat}
        </div>
    </div>
    """, unsafe_allow_html=True)

def _render_dupont_tab(ticker, info):
    _sec("Análisis DuPont (3 Etapas)")
    adv = valuation.compute_advanced_metrics(ticker)
    
    nm = adv.get("dupont_net_margin", 0)
    at = adv.get("dupont_asset_turnover", 0)
    em = adv.get("dupont_equity_multiplier", 0)
    roe = adv.get("dupont_roe", 0)
    
    if not roe:
        st.info("Datos insuficientes para realizar la descomposición DuPont.")
        return

    st.markdown(f"""
    <div style='text-align:center; margin-bottom:30px;'>
        <div style='font-size:13px; color:#5a6f8a; text-transform:uppercase;'>ROE Total</div>
        <div style='font-size:48px; font-weight:800; color:#34d399;'>{roe:.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

    d1, d2, d3 = st.columns(3)
    d1.markdown(kpi("Margen Neto", f"{nm:.2f}%", "Eficiencia Operativa", "blue"), unsafe_allow_html=True)
    d2.markdown(kpi("Rotación Activos", f"{at:.2f}x", "Uso de Activos", "purple"), unsafe_allow_html=True)
    d3.markdown(kpi("Mult. Capital", f"{em:.2f}x", "Apalancamiento", "#f97316"), unsafe_allow_html=True)
    
    # Waterfall chart
    fig_dup = go.Figure(go.Waterfall(
        name="ROE", orientation="v",
        measure=["relative", "relative", "relative", "total"],
        x=["Margen Neto", "Rotación", "Apalancamiento", "ROE"],
        y=[nm, at*10, em*5, roe], # Scaling for visual effect if needed
        connector={"line": {"color": "#475569"}},
        increasing={"marker": {"color": "#34d399"}},
        totals={"marker": {"color": "#60a5fa"}}
    ))
    fig_dup.update_layout(**dark_layout(height=400, title="Componentes del Retorno sobre Capital"))
    st.plotly_chart(fig_dup, use_container_width=True)

def _render_dividend_tab(ticker, info):
    _sec("Análisis de Dividendos & Aristocracia")
    
    div_yield = (info.get("dividendYield", 0) or 0) * 100
    payout = (info.get("payoutRatio", 0) or 0) * 100
    div_rate = info.get("dividendRate", 0) or 0
    
    if div_yield == 0:
        st.warning(f"{ticker} no paga dividendos actualmente.")
        return

    v1, v2, v3 = st.columns(3)
    v1.markdown(kpi("Dividend Yield", f"{div_yield:.2f}%", f"${div_rate:.2f} anual", "green"), unsafe_allow_html=True)
    
    p_col = "green" if payout < 60 else ("yellow" if payout < 85 else "red")
    v2.markdown(kpi("Payout Ratio (NI)", f"{payout:.1f}%", "Sobre Ben. Neto", p_col), unsafe_allow_html=True)
    
    # Advanced Dividends Data
    adv_div = valuation.compute_advanced_dividends(ticker)
    p_fcf = adv_div.get("payout_fcf")
    pf_col = "green" if p_fcf and p_fcf < 60 else ("yellow" if p_fcf and p_fcf < 90 else "red")
    v3.markdown(kpi("Payout Ratio (FCF)", f"{p_fcf:.1f}%" if p_fcf else "N/A", "Sobre Caja Real", pf_col), unsafe_allow_html=True)

    st.markdown("---")
    _sec("Proyecciones de Yield on Cost (YoC)")
    y1, y2, y3 = st.columns(3)
    dgr = adv_div.get("dgr_5y", 0)
    y1.markdown(kpi("DGR (5Y CAGR)", f"{dgr:.2f}%" if dgr else "N/A", "Crecimiento Div.", "blue"), unsafe_allow_html=True)
    y2.markdown(kpi("Yield on Cost (5Y)", f"{adv_div.get('yoc_5y') or 0:.2f}%", "Proyectado", "purple"), unsafe_allow_html=True)
    y3.markdown(kpi("Yield on Cost (10Y)", f"{adv_div.get('yoc_10y') or 0:.2f}%", "Proyectado", "purple"), unsafe_allow_html=True)

    st.markdown("### Crecimiento de Dividendos (CAGR)")
    try:
        tk = yf.Ticker(ticker)
        divs = tk.dividends
        if not divs.empty:
            divs_annual = divs.resample('Y').sum()
            if len(divs_annual) >= 5:
                fig_div = px.bar(divs_annual.tail(10), y='Dividends', title="Historial de Dividendos (Anual)", labels={'Dividends': 'USD', 'Date': 'Año'})
                fig_div.update_layout(**dark_layout(height=350))
                fig_div.update_traces(marker_color='#34d399')
                st.plotly_chart(fig_div, use_container_width=True)
                
                c5 = ((divs_annual.iloc[-1] / divs_annual.iloc[-6]) ** (1/5) - 1) * 100
                st.info(f"Crecimiento anual compuesto (CAGR 5Y): **{c5:.2f}%**")
    except:
        pass

    st.markdown("---")
    _sec("🛡️ Planificador de Independencia con " + ticker)
    with st.expander("Calcular libertad financiera con dividendos", expanded=True):
        f1, f2, f3 = st.columns(3)
        goal = f1.number_input("Objetivo Mensual ($)", 500, 50000, 2000, step=100)
        init = f2.number_input("Inversión Inicial ($)", 0, 1000000, 10000, step=1000)
        monthly = f3.number_input("Aporte Mensual ($)", 0, 10000, 500, step=100)
        
        # Simulation
        years = 30
        current_y = div_yield / 100
        tax = 0.15 # 15% dividend tax
        appreciation = 0.07 # 7% price growth
        dgr_rate = (dgr / 100) if (dgr is not None and dgr > 0) else 0.05
        
        data = []
        port = init
        target_met_year = None
        
        for y in range(1, years + 1):
            div_income_gross = port * current_y
            div_income_net = div_income_gross * (1 - tax)
            
            data.append({
                "Año": y,
                "Capital": round(port, 2),
                "Renta Mensual Neta": round(div_income_net / 12, 2)
            })
            
            if (div_income_net / 12) >= goal and target_met_year is None:
                target_met_year = y
            
            # Reinvest + Growth
            port = (port + div_income_net + (monthly * 12)) * (1 + appreciation)
            # DGR increases the yield over the original cost effectively
            current_y *= (1 + dgr_rate)

        df_sim = pd.DataFrame(data)
        
        st.markdown("#### Proyección de Ingresos Pasivos")
        fig_sim = px.area(df_sim, x="Año", y="Renta Mensual Neta", title=f"Renta Mensual Proyectada con {ticker}")
        fig_sim.add_hline(y=goal, line_dash="dash", line_color="white", annotation_text="Meta Mensual")
        fig_sim.update_layout(**dark_layout(height=350))
        st.plotly_chart(fig_sim, use_container_width=True)
        
        if target_met_year:
            st.success(f"🎯 **¡Meta Alcanzada!** Conseguirías tu libertad financiera con {ticker} en el año **{target_met_year}**.")
            st.caption(f"Aportando ${monthly}/mes y reinvirtiendo dividendos (estimado: {appreciation*100}% revalorización + {dgr}% crec. dividendo).")
        else:
            st.warning("⚠️ Con los parámetros actuales, no alcanzas la meta en los próximos 30 años. Intenta aumentar el aporte mensual.")

def _render_13f_tab(ticker, info):
    _sec("Smart Money: Vigilancia 13F")
    
    st.caption("Instituciones y Super-Inversores que mantienen esta posición según últimos reportes 13F.")
    
    try:
        from adapters.providers.stocks import inst_holders
        holders = yf.Ticker(ticker).institutional_holders
        if holders is not None and not holders.empty:
            st.dataframe(holders, use_container_width=True, hide_index=True)
            
            whales = ["Berkshire Hathaway", "Bridgewater", "Scion", "Pershing Square", "Bill & Melinda Gates"]
            match = holders[holders['Holder'].str.contains('|'.join(whales), case=False, na=False)]
            if not match.empty:
                st.success(f"🐋 **CONFLUENCIA ESTRATÉGICA:** Se detectó presencia de Super-Inversores ({', '.join(match['Holder'].tolist())})")
        else:
            st.info("No hay datos de tenencia institucional disponibles para este ticker.")
    except:
        st.info("Servidor de datos 13F temporalmente no disponible.")

def _render_magic_tab():
    _sec("🏆 Ranking Global: Magic Formula (Greenblatt)")
    st.caption("Clasificación de acciones en tu Watchlist basada en un alto rendimiento del capital (ROC) y beneficios baratos (Earnings Yield).")
    
    w_tickers = db.get_watchlist()["ticker"].tolist()
    if not w_tickers:
        st.info("Añade tickers a tu Watchlist para poder ver el ranking Magic Formula.")
        return
        
    if st.button("🚀 Generar / Actualizar Ranking Magic Formula"):
        with st.spinner("Analizando Watchlist..."):
            ranking = valuation.get_magic_formula_ranking(w_tickers)
            if not ranking.empty:
                st.success(f"Ranking completado con éxito para {len(ranking)} tickers.")
                st.dataframe(ranking, use_container_width=True, hide_index=True)
                
                # Visual comparison
                fig_mag = px.scatter(ranking, x="ROC (%)", y="Earnings Yield (%)", text="Ticker",
                                     title="Magic Formula: Calidad vs. Precio", color="Magic Score",
                                     color_continuous_scale="RdYlGn_r")
                fig_mag.update_layout(**dark_layout(height=500))
                st.plotly_chart(fig_mag, use_container_width=True)
            else:
                st.warning("No hay suficientes datos financieros en la Watchlist para generar el ranking.")
