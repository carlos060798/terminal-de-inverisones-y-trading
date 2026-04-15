"""
sections/macro_context.py — Macro Economic Context
FRED API (free key) for yield curve, CPI, unemployment, VIX, Fed Funds Rate.
Falls back to yfinance treasury symbols if FRED key not configured.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
from ui_shared import DARK, dark_layout, fmt, kpi
import ai_engine
import database as db
from finterm import charts as fc
import streamlit_antd_components as sac
import yfinance as yf

# Try FRED
try:
    from fredapi import Fred
    import services.fred_service as fred_service
    HAS_FRED = True
except ImportError:
    HAS_FRED = False


def _get_fred():
    """Get FRED client if API key is available."""
    if not HAS_FRED:
        return None
    try:
        key = st.secrets.get("FRED_API_KEY") or os.environ.get("FRED_API_KEY", "")
        if key:
            return Fred(api_key=key)
    except Exception:
        pass
    return None


def _fred_yield_curve(fred):
    """Fetch yield curve data from FRED."""
    maturities = {"3M": "GS3M", "6M": "GS6M", "1Y": "GS1", "2Y": "GS2",
                  "5Y": "GS5", "7Y": "GS7", "10Y": "GS10", "20Y": "GS20", "30Y": "GS30"}
    data = {}
    for label, series_id in maturities.items():
        try:
            s = fred.get_series(series_id, observation_start=datetime.now() - timedelta(days=30))
            if not s.empty:
                data[label] = s.dropna().iloc[-1]
        except Exception:
            continue
    return data


def _yf_yield_curve():
    """Fallback: yield curve from yfinance treasury ETFs."""
    symbols = {"3M": "^IRX", "5Y": "^FVX", "10Y": "^TNX", "30Y": "^TYX"}
    data = {}
    for label, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period="5d")
            if not h.empty:
                data[label] = h["Close"].iloc[-1]
        except Exception:
            continue
    return data


def _fred_liquidity_data(fred):
    """Extrae indicadores de Liquidez y Riesgo Sistémico desde FRED."""
    if fred is None:
        return {}
    
    indicators = {
        "WALCL": "Balance de la Reserva Federal (Total Assets)",
        "M2SL": "Oferta Monetaria M2 Real",
        "BAMLH0A0HYM2": "Spread Bonos Basura (Riesgo Crédito)",
        "UNRATE": "Tasa de Desempleo (Sahm Rule)"
    }
    
    results = {}
    for series_id, name in indicators.items():
        try:
            # Obtener el último año para trazar tendencia
            s = fred.get_series(series_id, observation_start=datetime.now() - timedelta(days=365))
            if not s.empty:
                s_clean = s.dropna()
                if not s_clean.empty:
                    results[series_id] = {
                        "name": name,
                        "current": s_clean.iloc[-1],
                        "previous": s_clean.iloc[-2] if len(s_clean) > 1 else s_clean.iloc[-1],
                        "history": s_clean
                    }
        except Exception as e:
            print(f"[FRED] Error en {series_id}: {e}")
            continue
            
    return results


def _interpret_yield_curve(data):
    """Auto-interpret yield curve shape."""
    if not data:
        return "Sin datos", "#475569"
    vals = list(data.values())
    labels = list(data.keys())

    # Check inversion (short > long)
    short = data.get("2Y") or data.get("3M")
    long = data.get("10Y")
    if short and long:
        if short > long:
            return "⚠️ CURVA INVERTIDA — Señal de posible recesión", "#f87171"
        elif short > long - 0.2:
            return "⚡ CURVA PLANA — Incertidumbre económica", "#fbbf24"
        else:
            return "✅ CURVA NORMAL — Expansión económica", "#34d399"
    return "Datos insuficientes", "#475569"


ECONOMIC_CALENDAR_2026 = [
    # Inflation & Cost of Living
    {"date": "2026-01-14", "event": "CPI Diciembre 2025", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-04-10", "event": "CPI Marzo 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-05-29", "event": "PCE Core Abril 2026", "impact": "High", "category": "Inflation", "fred_series": "PCEPILFE", "source": "BEA"},
    # Central Bank (FED)
    {"date": "2026-01-28", "event": "FOMC: Decisión de Tipos", "impact": "Critical", "category": "Monetary Policy", "fred_series": "FEDFUNDS", "source": "FED"},
    {"date": "2026-03-18", "event": "FOMC: Proyecciones Económicas", "impact": "Critical", "category": "Monetary Policy", "fred_series": "FEDFUNDS", "source": "FED"},
    {"date": "2026-05-06", "event": "FOMC: Decisión de Tipos", "impact": "High", "category": "Monetary Policy", "fred_series": "FEDFUNDS", "source": "FED"},
    # Labor Market
    {"date": "2026-04-03", "event": "Non-Farm Payrolls (NFP)", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-05-01", "event": "Non-Farm Payrolls (NFP)", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    # Economic Growth
    {"date": "2026-04-30", "event": "GDP Q1 2026 Advance", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    {"date": "2026-11-25", "event": "GDP Q3 2026 Preliminary", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
]


def _render_economic_calendar(fred):
    """Render the Economic Calendar tab with upcoming macro events."""
    from datetime import datetime, timedelta

    st.markdown("### Calendario Económico Proprietary")
    
    # Render Internal Calendar first
    cal_df = pd.DataFrame(ECONOMIC_CALENDAR_2026)
    st.dataframe(cal_df, use_container_width=True, hide_index=True)
    
    with st.expander("🌐 Ver Calendario en Tiempo Real (Investing.com)", expanded=False):
        st.components.v1.html("""
            <iframe src="https://sslecal2.investing.com?columns=exc_flags,exc_currency,exc_importance,exc_actual,exc_forecast,exc_previous&importance=2,3&features=datepicker,timezone&countries=5&calType=week&timeZone=58&lang=1" 
            width="100%" height="800" frameborder="0" allowtransparency="true" marginwidth="0" marginheight="0"></iframe>
        """, height=820)


@st.fragment
def render_sentiment_volatility():
    """Fragment for VIX and Sentiment analysis."""
    st.markdown("<div class='sec-title'>Monitor de Sentimiento y Volatilidad</div>", unsafe_allow_html=True)
    with st.spinner("Cargando VIX…"):
        try:
            vix_hist = yf.Ticker("^VIX").history(period="1y")
            sp_hist = yf.Ticker("^GSPC").history(period="1y")
        except Exception:
            st.error("Error al obtener datos de volatilidad.")
            return

    if not vix_hist.empty:
        vix_current = vix_hist["Close"].iloc[-1]
        vix_avg = vix_hist["Close"].mean()
        sp_current = sp_hist["Close"].iloc[-1] if not sp_hist.empty else 0
        sp_ytd = (sp_hist["Close"].iloc[-1] / sp_hist["Close"].iloc[0] - 1) * 100 if len(sp_hist) > 1 else 0

        # Interpretation
        if vix_current > 30:
            vix_status, vix_color, vix_msg = "MIEDO EXTREMO", "red", "Pánico en el mercado — Posible oportunidad de compra"
        elif vix_current > 20:
            vix_status, vix_color, vix_msg = "PRECAUCIÓN", "red", "Volatilidad elevada — Mercado nervioso"
        else:
            vix_status, vix_color, vix_msg = "NORMAL", "green", "Condiciones estables de mercado"

        vk1, vk2, vk3 = st.columns(3)
        vk1.markdown(kpi("VIX Actual", f"{vix_current:.1f}", vix_status, vix_color), unsafe_allow_html=True)
        vk2.markdown(kpi("VIX Promedio (1Y)", f"{vix_avg:.1f}", "", "blue"), unsafe_allow_html=True)
        vk3.markdown(kpi("S&P 500 YTD", f"{sp_ytd:+.1f}%", f"${sp_current:,.0f}", "green" if sp_ytd > 0 else "red"), unsafe_allow_html=True)

        st.info(f"💡 {vix_msg}")

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=vix_current,
            title=dict(text="Fear Index (VIX)", font=dict(color="#94a3b8", size=14)),
            gauge=dict(axis=dict(range=[0, 50]), bar=dict(color="#60a5fa"), bgcolor="#0a0a0a")
        ))
        fig_gauge.update_layout(**dark_layout(height=250))
        st.plotly_chart(fig_gauge, use_container_width=True)


@st.fragment
def render_currency_monitor():
    """Fragment for Currency Monitor."""
    st.markdown("<div class='sec-title'>Monitor de Divisas — Principales Pares</div>", unsafe_allow_html=True)
    _fx_pairs = {"EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X", "USD/MXN": "USDMXN=X"}
    _fx_data = {}
    with st.spinner("Descargando divisas..."):
        for label, sym in _fx_pairs.items():
            try:
                h = yf.Ticker(sym).history(period="5d")
                if not h.empty:
                    cur = h["Close"].iloc[-1]
                    prev = h["Close"].iloc[-2]
                    chg = ((cur - prev) / prev) * 100
                    _fx_data[label] = {"rate": cur, "change": chg}
            except: continue

    if _fx_data:
        cols = st.columns(len(_fx_data))
        for i, (pair, info) in enumerate(_fx_data.items()):
            color = "#34d399" if info["change"] >= 0 else "#f87171"
            cols[i].markdown(f"""
            <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:10px;padding:15px;text-align:center;'>
                <div style='font-size:10px;color:#5a6f8a;'>{pair}</div>
                <div style='font-size:18px;font-weight:700;'>{info["rate"]:.4f}</div>
                <div style='color:{color};font-size:11px;'>{info["change"]:+.2f}%</div>
            </div>""", unsafe_allow_html=True)


def render():
    st.markdown("""
    <div class="header-container">
      <div class="header-text">
        <h1>Contexto Macroeconómico</h1>
        <p>Yield Curve · Inflación · VIX · Indicadores de la Fed</p>
      </div>
    </div>""", unsafe_allow_html=True)

    fred = _get_fred()
    using_fred = fred is not None

    from services.fred_service import FREDUltraService
    service = FREDUltraService()
    
    _active_tab = sac.tabs([
        sac.TabsItem(label="🌊 Liquidez", icon="water"),
        sac.TabsItem(label="📊 Macro Ultra (80+)", icon="activity"),
        sac.TabsItem(label="📉 Recesión (Sahm)", icon="exclamation-triangle"),
        sac.TabsItem(label="📈 Buffett Indicator", icon="pie-chart"),
        sac.TabsItem(label="🤝 Correlación", icon="link"),
        sac.TabsItem(label="🎯 CMV Score", icon="target"),
        sac.TabsItem(label="📈 Yield Curve", icon="graph-up"),
        sac.TabsItem(label="😰 Sentimiento", icon="lightning-charge"),
        sac.TabsItem(label="📅 Calendario", icon="calendar-event"),
    ], color="blue", size="sm", return_index=False)

    # ══════════════════════════════════════════════════════════════
    # TAB 0: LIQUIDEZ Y RIESGO SISTÉMICO
    # ══════════════════════════════════════════════════════════════
    if _active_tab == "🌊 Liquidez":
        st.markdown("<div class='sec-title'>Radar de Liquidez de la FED & Riesgo Sistémico</div>", unsafe_allow_html=True)
        if using_fred:
            liq_data = _fred_liquidity_data(fred)
            if liq_data:
                lk1, lk2, lk3, lk4 = st.columns(4)
                # M2SL
                m2 = liq_data.get("M2SL", {})
                if m2:
                    val = m2['current']
                    pct = ((val - m2['previous']) / m2['previous']) * 100
                    lk1.markdown(kpi("M2 Money Supply", f"${val:,.0f}B", f"{pct:+.2f}%", "green" if pct > 0 else "red"), unsafe_allow_html=True)
                
                # WALCL
                walcl = liq_data.get("WALCL", {})
                if walcl:
                    val = walcl['current'] / 1000
                    pct = ((val - walcl['previous'] / 1000) / (walcl['previous'] / 1000)) * 100
                    lk2.markdown(kpi("Balance FED (WALCL)", f"${val:,.0f}B", f"{pct:+.2f}%", "green" if pct > 0 else "red"), unsafe_allow_html=True)
                
                # BAMLH0A0HYM2 (High Yield Spread)
                hy = liq_data.get("BAMLH0A0HYM2", {})
                if hy:
                    lk3.markdown(kpi("Spread Bonos Basura", f"{hy['current']:.2f}%", "Riesgo Crédito", "red" if hy['current'] > 5 else "green"), unsafe_allow_html=True)
                
                # UNRATE
                unr = liq_data.get("UNRATE", {})
                if unr:
                    lk4.markdown(kpi("Tasa Desempleo", f"{unr['current']:.1f}%", "Sahm Signal", "green"), unsafe_allow_html=True)
        else:
            st.error("Requiere API Key de FRED.")

    elif _active_tab == "📊 Macro Ultra (80+)":
        st.markdown("<div class='sec-title'>Explorador de Series FRED Ultra (+80)</div>", unsafe_allow_html=True)
        from services.fred_service import FRED_SERIES_ULTRA
        for cat, series in FRED_SERIES_ULTRA.items():
            with st.expander(f"{cat} ({len(series)} series)"):
                for sid, name in series.items():
                    st.write(f"**{sid}**: {name}")

    elif _active_tab == "📉 Recesión (Sahm)":
        st.markdown("<div class='sec-title'>Monitor de Recesión: Regla de Sahm</div>", unsafe_allow_html=True)
        sahm = service.calculate_sahm_rule()
        if sahm:
            c = "red" if sahm["is_recession"] else "green"
            st.markdown(kpi("Sahm Rule Indicator", f"{sahm['value']:+.2f}%", "RECESIÓN" if sahm["is_recession"] else "Estable", c), unsafe_allow_html=True)
            st.info("La Regla de Sahm identifica el inicio de una recesión cuando el promedio móvil de 3 meses de la tasa de desempleo nacional sube 0.5 puntos porcentuales o más por encima de su mínimo de los 12 meses anteriores.")

    elif _active_tab == "📈 Buffett Indicator":
        st.markdown("<div class='sec-title'>Valuación Global: Buffett Indicator</div>", unsafe_allow_html=True)
        buffett = service.calculate_buffett_indicator()
        if buffett:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(kpi("Mkt Cap / GDP", f"{buffett['ratio']:.1f}%", buffett['interpretation'], "blue"), unsafe_allow_html=True)
            with c2:
                st.info(f"""
                **Detalles del Modelo:**
                - Capitalización Mercado: ${buffett.get('mkt_cap', 0):,.0f}B
                - PIB Estimado: ${buffett.get('gdp', 0):,.0f}B
                - Interpretación: **{buffett['interpretation']}**
                """)
        else:
            st.warning("No se pudieron obtener datos para el Indicador Buffett. Verifica la API de FRED.")

    elif _active_tab == "🤝 Correlación":
        st.markdown("<div class='sec-title'>Matriz de Correlación Macro-Activos</div>", unsafe_allow_html=True)
        ticker = st.session_state.get("active_ticker", "SPY") or "SPY"
        from services.macro_stress_test import MacroStressEngine
        mse = MacroStressEngine()
        
        series_to_test = {
            "Tasas": "DGS10",
            "Inflación": "CPIAUCSL",
            "Liquidez": "M2SL",
            "Crédito": "BAMLH0A0HYM2",
            "Dólar": "DTWEXBGS"
        }
        
        corrs = []
        for label, sid in series_to_test.items():
            c = mse.get_ticker_macro_correlation(ticker, sid)
            corrs.append({"Serie Macro": label, "Correlación": c})
        
        df_corr = pd.DataFrame(corrs)
        st.table(df_corr)
        st.caption(f"Correlación histórica de {ticker} con variables principales.")

    elif _active_tab == "🎯 CMV Score":
        import services.macro_indicators as macro_indicators
        with st.spinner("Compilando Modelo CMV Aggregate..."):
            cmv_data = macro_indicators.get_cmv_indicators()
            
        if cmv_data:
            z_vals = [v['z'] for v in cmv_data.values()]
            agg_z = sum(z_vals) / len(z_vals) if z_vals else 0
            agg_label, agg_color, agg_icon = macro_indicators.get_rating_from_z(agg_z)
            
            st.markdown(f"""
            <div style='background:rgba({int(agg_color[1:3],16)},{int(agg_color[3:5],16)},{int(agg_color[5:7],16)},0.08);
                        border:1px solid {agg_color}30; border-radius:15px; padding:25px; margin-bottom:25px; text-align:center;'>
                <div style='font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:1.5px;'>CMV Aggregate Index</div>
                <div style='font-size:42px; font-weight:900; color:{agg_color}; margin:10px 0;'>{agg_z:+.2f}σ</div>
                <div style='font-size:18px; font-weight:700; color:white;'>{agg_icon} {agg_label}</div>
            </div>
            """, unsafe_allow_html=True)
            
            rows = [list(cmv_data.keys())[i:i+4] for i in range(0, len(cmv_data), 4)]
            for row_keys in rows:
                cols = st.columns(4)
                for i, k in enumerate(row_keys):
                    data = cmv_data[k]
                    label, color, icon = macro_indicators.get_rating_from_z(data['z'])
                    with cols[i]:
                        st.markdown(f"""
                        <div style='background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px; padding:15px; height:120px;'>
                            <div style='font-size:10px; color:#64748b; text-transform:uppercase;'>{k}</div>
                            <div style='font-size:16px; font-weight:700; color:white; margin:5px 0;'>{data['val']:.1f}{data['unit']}</div>
                            <div style='font-size:11px; font-weight:600; color:{color};'>{data['z']:+.1f}σ {icon}</div>
                        </div>
                        """, unsafe_allow_html=True)

    elif _active_tab == "📈 Yield Curve":
        yc_data = _fred_yield_curve(fred) if using_fred else _yf_yield_curve()
        if yc_data:
            st.plotly_chart(fc.create_yield_curve_chart(yc_data), use_container_width=True)

    elif _active_tab == "📊 Macro Ultra (80+)":
        st.markdown("<div class='sec-title'>Explorador Macro Pro (80+ Series)</div>", unsafe_allow_html=True)
        from services.fred_service import FRED_SERIES_ULTRA
        cat = st.selectbox("Seleccionar Categoría:", list(FRED_SERIES_ULTRA.keys()))
        series_dict = FRED_SERIES_ULTRA[cat]
        
        selected_label = st.selectbox("Seleccionar Indicador:", list(series_dict.values()))
        selected_id = [k for k, v in series_dict.items() if v == selected_label][0]
        
        with st.spinner(f"Extrayendo {selected_label}..."):
            df = service.get_series_ultra(selected_id)
            if not df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df["date"], y=df["value"], mode="lines", name=selected_label, line=dict(color="#3b82f6")))
                fig.update_layout(**dark_layout(height=450), title=f"Histórico: {selected_label}")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df.tail(20), use_container_width=True)

    elif _active_tab == "📉 Recesión (Sahm)":
        st.markdown("<div class='sec-title'>Monitor de Recesión: Regla de Sahm</div>", unsafe_allow_html=True)
        sahm = service.calculate_sahm_rule()
        if sahm:
            c1, c2 = st.columns(2)
            c1.metric("Sahm Value", f"{sahm['value']:.2f}%", delta="ALERTA" if sahm['is_recession'] else "Normal", delta_color="inverse" if sahm['is_recession'] else "normal")
            c2.metric("Desempleo Actual", f"{sahm['current_unrate']}%")
            
            st.info("La Regla de Sahm identifica señales de recesión cuando el promedio móvil de 3 meses de la tasa de desempleo aumenta en 0.5 puntos porcentuales o más por encima de su mínimo de los últimos 12 meses.")


    elif _active_tab == "🤝 Correlación":
        st.markdown("<div class='sec-title'>Matriz de Correlación: Macro vs Ticker</div>", unsafe_allow_html=True)
        ticker = st.text_input("Ingresar Ticker para Correlación:", value=st.session_state.get("active_ticker", "AAPL"))
        if ticker:
            from services.fred_service import FRED_SERIES_ULTRA
            cat = st.selectbox("Categoría Macro:", list(FRED_SERIES_ULTRA.keys()), key="cat_corr")
            series_id = st.selectbox("Indicador Macro:", list(FRED_SERIES_ULTRA[cat].keys()), format_func=lambda x: FRED_SERIES_ULTRA[cat][x], key="id_corr")
            
            if st.button("Calcular Correlación"):
                with st.spinner("Analizando series temporales..."):
                    res = service.get_macro_ticker_correlation(ticker, series_id)
                    if res:
                        st.markdown(f"### Correlación: **{res['correlation']:+.2f}**")
                        st.write(f"Interpretación: **{res['interpretation']}**")
                        st.caption(f"Basado en {res['sample_size']} puntos de datos (1 año).")
                    else:
                        st.error("No se pudieron alinear los datos para este ticker/indicador.")

    elif _active_tab == "🌍 Global":
        st.markdown("### Panorama Económico Global")
        m_df = db.get_macro_metrics()
        st.dataframe(m_df)

    elif _active_tab == "😰 Sentimiento":
        render_sentiment_volatility()

    elif _active_tab == "💱 Divisas":
        render_currency_monitor()

    elif _active_tab == "📅 Calendario":
        _render_economic_calendar(fred)

    # ── AI MACRO INSIGHTS ──
    st.markdown("---")
    if st.button("🤖 Generar Análisis Macro IA", use_container_width=True, type="primary"):
        from services.text_service import generate_macro_insight
        # Get basic context for the AI
        vix_val = 0
        try:
            vix_val = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]
        except: pass
        
        with st.spinner("Modelos de IA analizando contexto macroeconomico..."):
            insight, provider = generate_macro_insight(vix=vix_val)
            if insight:
                st.session_state["macro_ai_cache"] = {"insight": insight, "model": provider}
            
    if "macro_ai_cache" in st.session_state:
        cache_data = st.session_state["macro_ai_cache"]
        # Compatibility with older cache format
        if isinstance(cache_data, str):
            cache_data = {"insight": cache_data, "model": "Unknown Model"}
            
        st.markdown(f"""
        <div style="background:rgba(59, 130, 246, 0.05); border:1px solid rgba(59, 130, 246, 0.2); padding:20px; border-radius:12px; margin-top:20px;">
            <div style="color:#3b82f6; font-size:12px; font-weight:800; text-transform:uppercase; margin-bottom:10px;">Quantum Macro Intelligence</div>
            <div style="color:#e2e8f0; font-size:13px; line-height:1.6;">{cache_data['insight']}</div>
            <div style="color:#64748b; font-size:10px; margin-top:10px;">🤖 Generado por: {cache_data['model']}</div>
        </div>
        """, unsafe_allow_html=True)
