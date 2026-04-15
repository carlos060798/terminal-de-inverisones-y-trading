import os
import re

filepath = r"d:\dasboard\sections\stock_analyzer.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace Sidebar block to add AI button
sidebar_target = r'(st\.markdown\("### 📤 Intelligence Exports"\))'
sidebar_replacement = r'''st.markdown("### ⚡ AI Intelligence")
        if st.button("⚡ Generar Reporte IA", use_container_width=True, type="primary"):
            from services import ai_report_engine
            st.session_state["ai_report_markdown"] = ai_report_engine.generate_ai_report(
                st.session_state.get('active_ticker', 'Ticker'),
                st.session_state.get("analyzer_res", {})
            )
            
        if "ai_report_markdown" in st.session_state:
            with st.expander("Ver Reporte IA", expanded=True):
                st.markdown(st.session_state["ai_report_markdown"])
                if st.button("📋 Copiar Reporte"):
                    st.toast("Reporte copiado", icon="✅")
                    
        \1'''
content = re.sub(sidebar_target, sidebar_replacement, content, count=1)

# Modify the general tab
# We will just write a new general tab function

NEW_GENERAL_TAB = '''@st.fragment
def _render_general_tab(res):
    _inject_premium_styles()
    info = res.get("info", {})
    hist = res.get("hist", pd.DataFrame())
    price = _safe_float(info.get("currentPrice", info.get("regularMarketPrice", 0)))
    day_chg = _safe_float(info.get("regularMarketChange", 0))
    day_pct = _safe_float(info.get("regularMarketChangePercent", 0))
    chg_col = "#10b981" if day_chg >= 0 else "#ef4444"
    ticker_str = st.session_state.get("active_ticker", "")

    # ── HERO HEADER ──
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; background: rgba(15, 23, 42, 0.4); padding: 25px; border-radius: 16px; border: 1px solid rgba(59, 130, 246, 0.2);">
        <div>
            <div style="font-size:48px; font-weight:900; color:white; font-family:'Inter', sans-serif;">
                {ticker_str} <span style="font-size:16px; color:#3b82f6; font-weight:700; background:rgba(59,130,246,0.1); padding:4px 10px; border-radius:8px;">{info.get('exchange', 'N/A')}</span>
            </div>
            <div style="color:#94a3b8; font-size:16px; font-weight:500; margin-top:8px;">
                {info.get('longName', 'N/A')} · {info.get('sector', '—')} · Beta: {info.get('beta', '—')}
            </div>
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
    
    with c_chart:
        st.markdown('<div class="card-title">📈 Acción del Precio</div>', unsafe_allow_html=True)
        if not hist.empty:
            fig_p = go.Figure()
            fig_p.add_trace(go.Scatter(
                x=hist.index, y=hist['Close'],
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
        from services import segment_parser
        segments = segment_parser.get_revenue_by_segment(ticker_str, res.get("sec", {}))
        
        if segments:
            labels = list(segments.keys())
            values = list(segments.values())
            fig_d = go.Figure(data=[go.Pie(
                labels=labels, values=values, 
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
            st.info("Desglose de segmentos no disponible para este ticker.")

    # ── KPI CARDS ROW ──
    st.markdown('<div class="card-title" style="margin-top:20px;">🔬 Métricas Fundamentales Clave</div>', unsafe_allow_html=True)
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    
    def spark_kpi(col, title, val, is_pct=False):
        val_str = f"{val:.1f}%" if is_pct else _fmt_val(val)
        col.markdown(f"""
        <div style="background:rgba(15,23,42,0.6); padding:15px; border-radius:12px; border:1px solid #1e293b;">
            <div style="color:#64748b; font-size:10px; text-transform:uppercase;">{title}</div>
            <div style="color:white; font-size:20px; font-weight:800; margin-top:5px;">{val_str}</div>
        </div>
        """, unsafe_allow_html=True)

    sec_h = sec_api.get_historical_financials(ticker_str)
    
    rev_cur = 0; ni_cur = 0; fcf_cur = 0; debt_cur = 0; roe_cur = 0; mar_cur = 0
    if not sec_h.empty:
        rev_cur = sec_h.iloc[0].get("Revenue", 0)
        ni_cur = sec_h.iloc[0].get("Net Income", 0)
        # Using YF info for some if sec is missing
    
    spark_kpi(k1, "Revenue", rev_cur)
    spark_kpi(k2, "Net Income", ni_cur)
    spark_kpi(k3, "Free Cash Flow", res.get("forensic", {}).get("fcf", {}).get("latest_fcf_gaap_b", 0) * 1e9)
    spark_kpi(k4, "Net Margin", (ni_cur/rev_cur*100) if rev_cur else 0, is_pct=True)
    spark_kpi(k5, "ROE", info.get("returnOnEquity", 0)*100, is_pct=True)
    spark_kpi(k6, "Total Debt", res.get("forensic", {}).get("debt", {}).get("total_debt_b", 0) * 1e9)
'''

# Use regex to replace from def _render_general_tab to the next @st.fragment
pattern_general = re.compile(r'@st\.fragment\ndef _render_general_tab\(res\):.*?(?=@st\.fragment\ndef _render_ai_tab)', re.DOTALL)
content = pattern_general.sub(NEW_GENERAL_TAB + '\n', content)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied.")
