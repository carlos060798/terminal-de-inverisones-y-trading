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

# Try FRED
try:
    from fredapi import Fred
    HAS_FRED = True
except ImportError:
    HAS_FRED = False

import yfinance as yf


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
    # ── CPI Releases (12 months, High impact) ──
    {"date": "2026-01-14", "event": "CPI Diciembre 2025", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-02-12", "event": "CPI Enero 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-03-11", "event": "CPI Febrero 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-04-10", "event": "CPI Marzo 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-05-13", "event": "CPI Abril 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-06-10", "event": "CPI Mayo 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-07-14", "event": "CPI Junio 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-08-12", "event": "CPI Julio 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-09-11", "event": "CPI Agosto 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-10-13", "event": "CPI Septiembre 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-11-12", "event": "CPI Octubre 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    {"date": "2026-12-10", "event": "CPI Noviembre 2026", "impact": "High", "category": "Inflation", "fred_series": "CPIAUCSL", "source": "BLS"},
    # ── Non-Farm Payrolls (12 months, High impact) ──
    {"date": "2026-01-09", "event": "NFP Diciembre 2025", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-02-06", "event": "NFP Enero 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-03-06", "event": "NFP Febrero 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-04-03", "event": "NFP Marzo 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-05-08", "event": "NFP Abril 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-06-05", "event": "NFP Mayo 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-07-02", "event": "NFP Junio 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-08-07", "event": "NFP Julio 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-09-04", "event": "NFP Agosto 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-10-02", "event": "NFP Septiembre 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-11-06", "event": "NFP Octubre 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    {"date": "2026-12-04", "event": "NFP Noviembre 2026", "impact": "High", "category": "Employment", "fred_series": "PAYEMS", "source": "BLS"},
    # ── FOMC Decisions (8 meetings, High impact) ──
    {"date": "2026-01-28", "event": "FOMC Decisión Enero", "impact": "High", "category": "Fed", "fred_series": "FEDFUNDS", "source": "Federal Reserve"},
    {"date": "2026-03-18", "event": "FOMC Decisión Marzo", "impact": "High", "category": "Fed", "fred_series": "FEDFUNDS", "source": "Federal Reserve"},
    {"date": "2026-05-06", "event": "FOMC Decisión Mayo", "impact": "High", "category": "Fed", "fred_series": "FEDFUNDS", "source": "Federal Reserve"},
    {"date": "2026-06-17", "event": "FOMC Decisión Junio", "impact": "High", "category": "Fed", "fred_series": "FEDFUNDS", "source": "Federal Reserve"},
    {"date": "2026-07-29", "event": "FOMC Decisión Julio", "impact": "High", "category": "Fed", "fred_series": "FEDFUNDS", "source": "Federal Reserve"},
    {"date": "2026-09-16", "event": "FOMC Decisión Septiembre", "impact": "High", "category": "Fed", "fred_series": "FEDFUNDS", "source": "Federal Reserve"},
    {"date": "2026-11-04", "event": "FOMC Decisión Noviembre", "impact": "High", "category": "Fed", "fred_series": "FEDFUNDS", "source": "Federal Reserve"},
    {"date": "2026-12-16", "event": "FOMC Decisión Diciembre", "impact": "High", "category": "Fed", "fred_series": "FEDFUNDS", "source": "Federal Reserve"},
    # ── GDP Releases (4 advance + 4 preliminary, High impact) ──
    {"date": "2026-01-29", "event": "GDP Q4 2025 Advance", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    {"date": "2026-02-26", "event": "GDP Q4 2025 Preliminary", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    {"date": "2026-04-29", "event": "GDP Q1 2026 Advance", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    {"date": "2026-05-28", "event": "GDP Q1 2026 Preliminary", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    {"date": "2026-07-30", "event": "GDP Q2 2026 Advance", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    {"date": "2026-08-27", "event": "GDP Q2 2026 Preliminary", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    {"date": "2026-10-29", "event": "GDP Q3 2026 Advance", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    {"date": "2026-11-25", "event": "GDP Q3 2026 Preliminary", "impact": "High", "category": "Growth", "fred_series": "GDP", "source": "BEA"},
    # ── PPI Releases (12 months, Medium impact) ──
    {"date": "2026-01-15", "event": "PPI Diciembre 2025", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-02-13", "event": "PPI Enero 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-03-12", "event": "PPI Febrero 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-04-09", "event": "PPI Marzo 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-05-14", "event": "PPI Abril 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-06-11", "event": "PPI Mayo 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-07-15", "event": "PPI Junio 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-08-13", "event": "PPI Julio 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-09-14", "event": "PPI Agosto 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-10-14", "event": "PPI Septiembre 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-11-13", "event": "PPI Octubre 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    {"date": "2026-12-11", "event": "PPI Noviembre 2026", "impact": "Medium", "category": "Inflation", "fred_series": "PPIACO", "source": "BLS"},
    # ── ISM Manufacturing (6 selected months, Medium impact) ──
    {"date": "2026-01-05", "event": "ISM Manufactura Diciembre", "impact": "Medium", "category": "Manufacturing", "fred_series": None, "source": "ISM"},
    {"date": "2026-03-02", "event": "ISM Manufactura Febrero", "impact": "Medium", "category": "Manufacturing", "fred_series": None, "source": "ISM"},
    {"date": "2026-05-01", "event": "ISM Manufactura Abril", "impact": "Medium", "category": "Manufacturing", "fred_series": None, "source": "ISM"},
    {"date": "2026-07-01", "event": "ISM Manufactura Junio", "impact": "Medium", "category": "Manufacturing", "fred_series": None, "source": "ISM"},
    {"date": "2026-09-01", "event": "ISM Manufactura Agosto", "impact": "Medium", "category": "Manufacturing", "fred_series": None, "source": "ISM"},
    {"date": "2026-11-02", "event": "ISM Manufactura Octubre", "impact": "Medium", "category": "Manufacturing", "fred_series": None, "source": "ISM"},
    # ── Retail Sales (6 selected months, Medium impact) ──
    {"date": "2026-01-16", "event": "Ventas Minoristas Diciembre", "impact": "Medium", "category": "Consumer", "fred_series": "RSAFS", "source": "BLS"},
    {"date": "2026-03-17", "event": "Ventas Minoristas Febrero", "impact": "Medium", "category": "Consumer", "fred_series": "RSAFS", "source": "BLS"},
    {"date": "2026-05-15", "event": "Ventas Minoristas Abril", "impact": "Medium", "category": "Consumer", "fred_series": "RSAFS", "source": "BLS"},
    {"date": "2026-07-16", "event": "Ventas Minoristas Junio", "impact": "Medium", "category": "Consumer", "fred_series": "RSAFS", "source": "BLS"},
    {"date": "2026-09-16", "event": "Ventas Minoristas Agosto", "impact": "Medium", "category": "Consumer", "fred_series": "RSAFS", "source": "BLS"},
    {"date": "2026-11-17", "event": "Ventas Minoristas Octubre", "impact": "Medium", "category": "Consumer", "fred_series": "RSAFS", "source": "BLS"},
    # ── Consumer Confidence (6 selected months, Medium impact) ──
    {"date": "2026-01-27", "event": "Confianza Consumidor Enero", "impact": "Medium", "category": "Consumer", "fred_series": None, "source": "Conference Board"},
    {"date": "2026-03-31", "event": "Confianza Consumidor Marzo", "impact": "Medium", "category": "Consumer", "fred_series": None, "source": "Conference Board"},
    {"date": "2026-05-26", "event": "Confianza Consumidor Mayo", "impact": "Medium", "category": "Consumer", "fred_series": None, "source": "Conference Board"},
    {"date": "2026-07-28", "event": "Confianza Consumidor Julio", "impact": "Medium", "category": "Consumer", "fred_series": None, "source": "Conference Board"},
    {"date": "2026-09-29", "event": "Confianza Consumidor Septiembre", "impact": "Medium", "category": "Consumer", "fred_series": None, "source": "Conference Board"},
    {"date": "2026-11-24", "event": "Confianza Consumidor Noviembre", "impact": "Medium", "category": "Consumer", "fred_series": None, "source": "Conference Board"},
]


def _render_economic_calendar(fred):
    """Render the Economic Calendar tab with upcoming macro events."""
    from datetime import datetime, timedelta

    st.markdown("### Calendario Económico")
    
    with st.expander("📊 Ver Calendario en Tiempo Real (Investing.com)", expanded=True):
        st.components.v1.html("""
            <iframe src="https://sslecal2.investing.com?columns=exc_flags,exc_currency,exc_importance,exc_actual,exc_forecast,exc_previous&importance=2,3&features=datepicker,timezone&countries=5&calType=week&timeZone=58&lang=1" 
            width="100%" height="800" frameborder="0" allowtransparency="true" marginwidth="0" marginheight="0"></iframe>
        """, height=820)

    st.markdown("---")
    st.markdown("#### Programación de Eventos Clave 2026")

    today = datetime.now().date()
    week_end = today + timedelta(days=7)

    cal_df = pd.DataFrame(ECONOMIC_CALENDAR_2026)
    cal_df["date"] = pd.to_datetime(cal_df["date"]).dt.date
    cal_df = cal_df.sort_values("date")

    # Status column
    def get_status(d):
        if d < today:
            return "Pasado"
        if d <= week_end:
            return "Esta Semana"
        return "Pr\u00f3ximo"

    cal_df["status"] = cal_df["date"].apply(get_status)

    # KPIs
    upcoming = cal_df[cal_df["date"] >= today]
    this_week = cal_df[(cal_df["date"] >= today) & (cal_df["date"] <= week_end)]
    high_upcoming = upcoming[upcoming["impact"] == "High"]

    k1, k2, k3 = st.columns(3)
    k1.markdown(kpi(
        "Pr\u00f3ximo Evento",
        upcoming.iloc[0]["event"][:20] if not upcoming.empty else "N/A",
        str(upcoming.iloc[0]["date"]) if not upcoming.empty else "",
        "blue"
    ), unsafe_allow_html=True)
    k2.markdown(kpi(
        "Esta Semana",
        str(len(this_week)),
        "eventos",
        "purple"
    ), unsafe_allow_html=True)
    k3.markdown(kpi(
        "High Impact Pendiente",
        str(len(high_upcoming)),
        "eventos",
        "red"
    ), unsafe_allow_html=True)

    # Filters
    fc1, fc2 = st.columns(2)
    impact_sel = fc1.multiselect(
        "Impacto", ["High", "Medium", "Low"],
        default=["High", "Medium"], key="cal_impact"
    )
    cats = cal_df["category"].unique().tolist()
    cat_sel = fc2.multiselect(
        "Categor\u00eda", cats, default=cats, key="cal_cat"
    )

    filtered = cal_df[
        (cal_df["impact"].isin(impact_sel)) & (cal_df["category"].isin(cat_sel))
    ]

    # Status styling function
    def status_style(v):
        if v == "Pasado":
            return "color: #475569"
        if v == "Esta Semana":
            return "background-color: rgba(251,191,36,0.15); color: #fbbf24; font-weight: 600"
        return "color: #e2e8f0"

    display = filtered[["date", "event", "category", "impact", "status", "source"]].copy()
    display.columns = ["Fecha", "Evento", "Categor\u00eda", "Impacto", "Estado", "Fuente"]

    styled = display.style.map(status_style, subset=["Estado"])
    st.dataframe(styled, use_container_width=True, hide_index=True, height=400)

    # Historical context
    st.markdown("---")
    st.markdown("**Contexto Hist\u00f3rico**")
    fred_events = filtered[filtered["fred_series"].notna()]["event"].unique().tolist()
    if fred_events and fred:
        selected_event = st.selectbox(
            "Ver serie hist\u00f3rica", [""] + fred_events, key="cal_hist"
        )
        if selected_event:
            evt_row = filtered[filtered["event"] == selected_event].iloc[0]
            series_id = evt_row["fred_series"]
            try:
                hist = fred.get_series(
                    series_id,
                    observation_start=datetime.now() - timedelta(days=365 * 3)
                )
                if hist is not None and not hist.empty:
                    fig = fc.create_historical_chart(hist, f"{selected_event} ({series_id})")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning(f"No se pudo generar el gráfico para {series_id}")
                else:
                    st.warning(f"No hay datos históricos para {series_id}")
            except Exception as e:
                st.warning(f"Error cargando {series_id}: {e}")
    elif not fred:
        st.info("Conecta tu API key de FRED para ver series históricas de cada evento.")


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Contexto Macroeconómico</h1>
        <p>Yield Curve · Inflación · VIX · Indicadores de la Fed</p>
      </div>
    </div>""", unsafe_allow_html=True)

    fred = _get_fred()
    using_fred = fred is not None

    if using_fred:
        st.markdown("""
        <div style='background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.3);
                    border-radius:10px;padding:10px 16px;margin-bottom:16px;color:#86efac;font-size:12px;'>
          📡 Conectado a FRED (Federal Reserve Economic Data) — Datos oficiales
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.3);
                    border-radius:10px;padding:10px 16px;margin-bottom:16px;color:#fde047;font-size:12px;'>
          ⚡ Sin API key de FRED — Usando datos de yfinance (limitados).<br>
          Para datos completos: registra tu key gratis en
          <a href="https://fred.stlouisfed.org/docs/api/api_key.html" target="_blank" style="color:#60a5fa;">fred.stlouisfed.org</a>
          y agrégala en <code>.streamlit/secrets.toml</code>
        </div>""", unsafe_allow_html=True)

    tab_liq, tab_cmv, tab_yield, tab_macro, tab_global, tab_vix, tab_fx, tab_cal = st.tabs([
        "🌊 Liquidez & Riesgo", "🎯 CMV Score", "📈 Yield Curve", "📊 Indicadores Macro", "🌍 Contexto Global (WB)", 
        "😰 VIX & Sentimiento", "💱 Monitor de Divisas", "📅 Calendario Económico"
    ])

    # ══════════════════════════════════════════════════════════════
    # TAB 0: LIQUIDEZ Y RIESGO SISTÉMICO (MACRO M2 / WALCL)
    # ══════════════════════════════════════════════════════════════
    with tab_liq:
        st.markdown("<div class='sec-title'>Radar de Liquidez de la FED & Riesgo Sistémico</div>", unsafe_allow_html=True)
        if using_fred:
            with st.spinner("Descargando data de Liquidez (M2, WALCL, Sahm Rule)..."):
                liq_data = _fred_liquidity_data(fred)
            
            if liq_data:
                lk1, lk2, lk3, lk4 = st.columns(4)
                
                # M2SL
                m2 = liq_data.get("M2SL", {})
                if m2:
                    val = m2['current']
                    pct = ((val - m2['previous']) / m2['previous']) * 100
                    c = "green" if pct > 0 else "red"
                    lk1.markdown(kpi("M2 Money Supply", f"${val:,.0f}B", f"{pct:+.2f}%", c), unsafe_allow_html=True)
                
                # WALCL
                walcl = liq_data.get("WALCL", {})
                if walcl:
                    val = walcl['current'] / 1000 # Convert to Billions
                    prev = walcl['previous'] / 1000
                    pct = ((val - prev) / prev) * 100
                    c = "green" if pct > 0 else "red"
                    lk2.markdown(kpi("Balance FED (WALCL)", f"${val:,.0f}B", f"{pct:+.2f}%", c), unsafe_allow_html=True)
                
                # BAMLH0A0HYM2 (High Yield Spread)
                hy = liq_data.get("BAMLH0A0HYM2", {})
                if hy:
                    val = hy['current']
                    prev = hy['previous']
                    pct = val - prev
                    c = "red" if pct > 0 else "green" # Riesgo sube es malo
                    lk3.markdown(kpi("Spread Bonos Basura", f"{val:,.2f}%", f"{pct:+.2f} bps", c), unsafe_allow_html=True)

                # UNRATE (Desempleo)
                unr = liq_data.get("UNRATE", {})
                if unr:
                    val = unr['current']
                    prev = unr['previous']
                    pct = val - prev
                    c = "red" if pct > 0 else "green"
                    lk4.markdown(kpi("Tasa Desempleo", f"{val:,.1f}%", f"{pct:+.1f}% Sahm", c), unsafe_allow_html=True)
                
                # Graficar WALCL (Inyección de Dinero)
                if walcl:
                    hist = walcl['history']
                    fig_walcl = go.Figure()
                    fig_walcl.add_trace(go.Scatter(
                        x=hist.index, y=hist.values / 1000, mode="lines",
                        line=dict(color="#10b981", width=2),
                        fill="tozeroy", fillcolor="rgba(16,185,129,0.1)",
                    ))
                    fig_walcl.update_layout(**DARK, height=350,
                        title="Impresión de Dinero: Balance Total de la FED (Billones USD)",
                        yaxis_title="Billones ($)", showlegend=False)
                    st.plotly_chart(fig_walcl, use_container_width=True)
            else:
                st.warning("No se pudo obtener datos de Liquidez desde FRED API.")
        else:
            st.error("Rastreo de Inyección M2 y Balance FED requiere una API Key gratuita de FRED.")

    # ══════════════════════════════════════════════════════════════
    # TAB 1: CMV SCORE (VALORACIÓN AGREGADA)
    # ══════════════════════════════════════════════════════════════
    with tab_cmv:
        import services.macro_indicators as macro_indicators
        
        with st.spinner("Compilando Modelo CMV Aggregate..."):
            cmv_data = macro_indicators.get_cmv_indicators()
            
        if cmv_data:
            # Aggregate Index = Mean of Z-scores
            z_vals = [v['z'] for v in cmv_data.values()]
            agg_z = sum(z_vals) / len(z_vals) if z_vals else 0
            agg_label, agg_color, agg_icon = macro_indicators.get_rating_from_z(agg_z)
            
            # Header Gauge
            st.markdown(f"""
            <div style='background:rgba({int(agg_color[1:3],16)},{int(agg_color[3:5],16)},{int(agg_color[5:7],16)},0.08);
                        border:1px solid {agg_color}30; border-radius:15px; padding:25px; margin-bottom:25px; text-align:center;'>
                <div style='font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:1.5px;'>CMV Aggregate Market Value Index</div>
                <div style='font-size:42px; font-weight:900; color:{agg_color}; margin:10px 0;'>{agg_z:+.2f}σ</div>
                <div style='font-size:18px; font-weight:700; color:white;'>{agg_icon} {agg_label}</div>
                <div style='font-size:12px; color:#64748b; margin-top:10px;'>Promedio de desviación estándar de 14 indicadores fundamentales</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Grid of Indicators
            st.markdown("<div style='margin-bottom:15px; font-weight:600; color:#94a3b8;'>Componentes del Modelo</div>", unsafe_allow_html=True)
            
            rows = [list(cmv_data.keys())[i:i+4] for i in range(0, len(cmv_data), 4)]
            for row_keys in rows:
                cols = st.columns(4)
                for i, k in enumerate(row_keys):
                    data = cmv_data[k]
                    z = data['z']
                    val = data['val']
                    unit = data['unit']
                    label, color, icon = macro_indicators.get_rating_from_z(z)
                    
                    with cols[i]:
                        st.markdown(f"""
                        <div style='background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px; padding:15px; height:140px;'>
                            <div style='font-size:10px; color:#64748b; text-transform:uppercase; margin-bottom:5px;'>{k}</div>
                            <div style='font-size:18px; font-weight:700; color:white;'>{val:.1f}{unit}</div>
                            <div style='font-size:12px; font-weight:600; color:{color}; margin-top:8px;'>{z:+.1f}σ {icon}</div>
                            <div style='font-size:9px; color:#475569; margin-top:4px;'>{label}</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("""
            <div style='color:#64748b; font-size:11px;'>
                Metodología basada en Current Market Valuation (CMV). Los indicadores se miden por su desviación estándar (σ) 
                respecto a su tendencia histórica de 20 años. Los datos se actualizan semanalmente vía FRED y yfinance.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("No se pudieron cargar los indicadores CMV.")

    # ══════════════════════════════════════════════════════════════
    # TAB 1: YIELD CURVE
    # ══════════════════════════════════════════════════════════════
    with tab_yield:
        with st.spinner("Obteniendo curva de rendimiento…"):
            yc_data = _fred_yield_curve(fred) if using_fred else _yf_yield_curve()

        if yc_data:
            interpretation, interp_color = _interpret_yield_curve(yc_data)

            # Interpretation badge
            st.markdown(f"""
            <div style='background:rgba({interp_color[1:][:2]},{interp_color[1:][2:4]},{interp_color[1:][4:]},0.1);
                        border:1px solid {interp_color}40;border-radius:12px;padding:16px;margin-bottom:20px;text-align:center;'>
              <span style='color:{interp_color};font-weight:700;font-size:16px;'>{interpretation}</span>
            </div>""", unsafe_allow_html=True)

            # KPIs
            yk1, yk2, yk3, yk4 = st.columns(4)
            if "2Y" in yc_data:
                yk1.markdown(kpi("Treasury 2Y", f"{yc_data['2Y']:.2f}%", "", "blue"), unsafe_allow_html=True)
            if "5Y" in yc_data:
                yk2.markdown(kpi("Treasury 5Y", f"{yc_data['5Y']:.2f}%", "", "blue"), unsafe_allow_html=True)
            if "10Y" in yc_data:
                yk3.markdown(kpi("Treasury 10Y", f"{yc_data['10Y']:.2f}%", "", "purple"), unsafe_allow_html=True)
            if "30Y" in yc_data:
                yk4.markdown(kpi("Treasury 30Y", f"{yc_data['30Y']:.2f}%", "", "purple"), unsafe_allow_html=True)

            # Usamos el componente institucional de curva de rendimientos
            fig_yc = fc.create_yield_curve_chart(yc_data)
            if fig_yc:
                st.plotly_chart(fig_yc, use_container_width=True)
            else:
                st.warning("No se pudo generar el gráfico de la curva de rendimientos.")

            # Historical 10Y if FRED
            if using_fred:
                try:
                    hist_10y = fred.get_series("GS10", observation_start=datetime.now() - timedelta(days=365*2))
                    if not hist_10y.empty:
                        fig_10y = fc.create_historical_chart(hist_10y, "Treasury 10Y — Últimos 2 años", color="#a78bfa")
                        st.plotly_chart(fig_10y, use_container_width=True)
                except Exception:
                    pass
        else:
            st.warning("No se pudieron obtener datos de la curva de rendimiento.")

    # ══════════════════════════════════════════════════════════════
    # TAB 2: INDICADORES MACRO (CPI, Unemployment, Fed Funds)
    # ══════════════════════════════════════════════════════════════
    with tab_macro:
        if using_fred:
            with st.spinner("Cargando indicadores macro..."):
                # Preparamos el diccionario de datos para el multi-chart
                macro_data = {}
                indicators_to_fetch = {
                    "Fed Funds": "FEDFUNDS",
                    "CPI Inflación %": "CPIAUCSL",
                    "Tasa Desempleo": "UNRATE",
                    "Liquidez M2": "M2SL"
                }
                
                for label, s_id in indicators_to_fetch.items():
                    try:
                        s = fred.get_series(s_id, observation_start=datetime.now() - timedelta(days=365*4))
                        if not s.empty:
                            if label == "CPI Inflación %":
                                # Convertir CPI a YoY
                                s = s.pct_change(12).dropna() * 100
                            macro_data[label] = s
                    except: continue
                
                if macro_data:
                    fig_multi = fc.create_macro_multi_chart(macro_data)
                    if fig_multi:
                        st.plotly_chart(fig_multi, use_container_width=True)
                    else:
                        st.warning("Error al procesar los indicadores macro para visualización.")
                else:
                    st.warning("No se pudieron cargar los datos macro (posible error de conexión o API Key inválida).")
        else:
            st.info("Indicadores macro (CPI, Desempleo, Fed Funds) requieren API Key de FRED.")
            st.markdown("""
            **Cómo obtener tu key gratuita:**
            1. Ve a [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)
            2. Crea una cuenta gratuita
            3. Solicita tu API key
            4. Agrégala en `.streamlit/secrets.toml`:
            ```
            FRED_API_KEY = "tu_key_aqui"
            ```
            """)

    # ══════════════════════════════════════════════════════════════
    # TAB: CONTEXTO GLOBAL (WORLD BANK)
    # ══════════════════════════════════════════════════════════════
    with tab_global:
        st.markdown("### 🌍 Panorama Económico Global (World Bank)")
        st.markdown("<div style='color:#94a3b8; font-size:13px; margin-bottom:15px;'>"
                   "Comparativa de indicadores estructurales de las principales potencias mundiales. "
                   "Datos de baja frecuencia (Anual/Trimestral) sincronizados periódicamente.</div>", unsafe_allow_html=True)
        
        try:
            m_df = db.get_macro_metrics()
            if not m_df.empty:
                indicators = sorted(m_df['indicator'].unique().tolist())
                sel_ind = st.selectbox("Seleccionar Indicador", indicators, key="wb_ind_sel")
                
                filtered_wb = m_df[m_df['indicator'] == sel_ind]
                if not filtered_wb.empty:
                    latest_year = filtered_wb['year'].max()
                    latest_data = filtered_wb[filtered_wb['year'] == latest_year].sort_values('value', ascending=False)
                    
                    fig_wb = go.Figure(go.Bar(
                        x=latest_data['country'],
                        y=latest_data['value'],
                        marker_color='#60a5fa',
                        text=latest_data['value'].apply(lambda x: f"{x:.1f}%"),
                        textposition='auto',
                    ))
                    fig_wb.update_layout(dark_layout(height=350, margin=dict(l=0, r=0, t=30, b=0)),
                                        title=dict(text=f"{sel_ind} (% Anual) - Año {latest_year}", 
                                                  font=dict(size=14, color="#94a3b8")))
                    st.plotly_chart(fig_wb, use_container_width=True)
                    
                    with st.expander("📊 Ver Histórico por Países"):
                        pivot_wb = filtered_wb.pivot(index='year', columns='country', values='value').sort_index(ascending=False)
                        st.dataframe(pivot_wb.style.format("{:.2f}%"), use_container_width=True)
            else:
                st.info("No hay datos globales sincronizados. Esperando al próximo ciclo de tareas...")
                if st.button("Lanzar Ingesta Macro WB Ahora"):
                    from services.data_ingestion.macro_service import sync_worldbank_macro
                    with st.spinner("Descargando datos macro globales..."):
                        if sync_worldbank_macro():
                            st.rerun()
        except Exception as e:
            st.error(f"Error cargando datos macro globales: {e}")

    # ══════════════════════════════════════════════════════════════
    # TAB 3: VIX & SENTIMIENTO
    # ══════════════════════════════════════════════════════════════
    with tab_vix:
        with st.spinner("Cargando VIX…"):
            try:
                vix_hist = yf.Ticker("^VIX").history(period="1y")
                sp_hist = yf.Ticker("^GSPC").history(period="1y")
            except Exception:
                vix_hist = pd.DataFrame()
                sp_hist = pd.DataFrame()

        if not vix_hist.empty:
            vix_current = vix_hist["Close"].iloc[-1]
            vix_avg = vix_hist["Close"].mean()
            sp_current = sp_hist["Close"].iloc[-1] if not sp_hist.empty else 0
            sp_ytd = 0
            if not sp_hist.empty and len(sp_hist) > 1:
                sp_ytd = (sp_hist["Close"].iloc[-1] / sp_hist["Close"].iloc[0] - 1) * 100

            # VIX interpretation
            if vix_current > 30:
                vix_status = "MIEDO EXTREMO"
                vix_color = "red"
                vix_msg = "Pánico en el mercado — Posible oportunidad de compra (Buffett: 'Be greedy when others are fearful')"
            elif vix_current > 20:
                vix_status = "PRECAUCIÓN"
                vix_color = "red"
                vix_msg = "Volatilidad elevada — Mercado nervioso, gestionar riesgo"
            elif vix_current > 15:
                vix_status = "NORMAL"
                vix_color = "blue"
                vix_msg = "Volatilidad normal — Condiciones estables de mercado"
            else:
                vix_status = "COMPLACENCIA"
                vix_color = "green"
                vix_msg = "Baja volatilidad — Mercado calmado, ojo con reversiones"

            # KPIs
            vk1, vk2, vk3 = st.columns(3)
            vk1.markdown(kpi("VIX Actual", f"{vix_current:.1f}", vix_status, vix_color), unsafe_allow_html=True)
            vk2.markdown(kpi("VIX Promedio (1Y)", f"{vix_avg:.1f}", "", "blue"), unsafe_allow_html=True)
            vk3.markdown(kpi("S&P 500 YTD", f"{sp_ytd:+.1f}%", f"${sp_current:,.0f}",
                            "green" if sp_ytd > 0 else "red"), unsafe_allow_html=True)

            # Interpretation
            st.markdown(f"""
            <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                        border-radius:12px;padding:16px;margin:16px 0;color:#94a3b8;font-size:13px;'>
              💡 <strong>{vix_msg}</strong>
            </div>""", unsafe_allow_html=True)

            # VIX Gauge
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=vix_current,
                number=dict(font=dict(color="#f0f6ff", size=36)),
                title=dict(text="Índice de Miedo (VIX)", font=dict(color="#94a3b8", size=14)),
                gauge=dict(
                    axis=dict(range=[0, 50], tickcolor="#475569",
                             tickfont=dict(color="#475569", size=10)),
                    bar=dict(color="#60a5fa", thickness=0.6),
                    bgcolor="#0a0a0a",
                    bordercolor="#1a1a1a",
                    steps=[
                        dict(range=[0, 15], color="rgba(52,211,153,0.15)"),
                        dict(range=[15, 20], color="rgba(96,165,250,0.15)"),
                        dict(range=[20, 30], color="rgba(251,191,36,0.15)"),
                        dict(range=[30, 50], color="rgba(248,113,113,0.15)"),
                    ],
                    threshold=dict(line=dict(color="#fbbf24", width=2),
                                  thickness=0.75, value=20),
                )
            ))
            fig_gauge.update_layout(**dark_layout(height=280, margin=dict(l=30, r=30, t=50, b=10)))
            st.plotly_chart(fig_gauge, use_container_width=True)

            # VIX + S&P500 chart
            vc1, vc2 = st.columns(2)
            with vc1:
                fig_vix = go.Figure()
                fig_vix.add_trace(go.Scatter(
                    x=vix_hist.index, y=vix_hist["Close"],
                    mode="lines", line=dict(color="#f87171", width=1.5),
                    fill="tozeroy", fillcolor="rgba(248,113,113,0.06)",
                ))
                fig_vix.add_hline(y=20, line_dash="dot", line_color="#fbbf24", line_width=0.8,
                                 annotation_text="Alerta (20)")
                fig_vix.add_hline(y=30, line_dash="dot", line_color="#f87171", line_width=0.8,
                                 annotation_text="Pánico (30)")
                fig_vix.update_layout(**DARK, height=300,
                    title=dict(text="VIX — 1 Año", font=dict(color="#94a3b8", size=13), x=0.5),
                    showlegend=False)
                st.plotly_chart(fig_vix, use_container_width=True)

            with vc2:
                if not sp_hist.empty:
                    fig_sp = go.Figure()
                    fig_sp.add_trace(go.Scatter(
                        x=sp_hist.index, y=sp_hist["Close"],
                        mode="lines", line=dict(color="#34d399", width=1.5),
                        fill="tozeroy", fillcolor="rgba(52,211,153,0.06)",
                    ))
                    fig_sp.update_layout(**DARK, height=300,
                        title=dict(text="S&P 500 — 1 Año", font=dict(color="#94a3b8", size=13), x=0.5),
                        showlegend=False)
                    st.plotly_chart(fig_sp, use_container_width=True)

            # ── AI MACRO INSIGHT ──
            providers = ai_engine.get_available_providers()
            if providers:
                st.markdown("<div class='sec-title' style='margin-top:20px;'>🧠 Investigación AI Fundamental y Macro</div>", unsafe_allow_html=True)
                user_query_macro = st.text_input("💭 Pregunta Macro / Fundamental (opcional):", placeholder="ej. ¿Cómo afecta la curva plana a los bancos esta semana?", key="macro_ai_query")
                
                if st.button("Procesar Investigación con IA"):
                    with st.spinner("Generando análisis macroeconómico…"):
                        ai_result = ai_engine.generate_macro_insight(
                            vix=vix_current,
                            sp500_ytd=sp_ytd,
                            user_query=user_query_macro
                        )
                        if ai_result:
                            st.markdown(f"""<div style='background:rgba(96,165,250,0.06);border:1px solid rgba(96,165,250,0.2);
                                        border-radius:14px;padding:20px;color:#c8d6e5;font-size:13px;line-height:1.7;'>
                              {ai_result}
                            </div>""", unsafe_allow_html=True)
        else:
            st.warning("No se pudieron obtener datos del VIX.")

    # ══════════════════════════════════════════════════════════════
    # TAB 4: CURRENCY MONITOR (Bloomberg-style)
    # ══════════════════════════════════════════════════════════════
    with tab_fx:
        try:
            import plotly.graph_objects as _go_fx

            st.markdown("<div class='sec-title'>Monitor de Divisas — Principales Pares</div>", unsafe_allow_html=True)

            _fx_pairs = {
                "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
                "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X",
                "USD/MXN": "USDMXN=X", "USD/BRL": "USDBRL=X",
            }
            _fx_data = {}
            with st.spinner("Descargando datos de divisas..."):
                for _label, _sym in _fx_pairs.items():
                    try:
                        _h = yf.Ticker(_sym).history(period="5d")
                        if not _h.empty and len(_h) >= 2:
                            _cur = _h["Close"].iloc[-1]
                            _prev = _h["Close"].iloc[-2]
                            _chg = ((_cur - _prev) / _prev) * 100
                            _fx_data[_label] = {"rate": float(_cur), "change": float(_chg), "symbol": _sym}
                        elif not _h.empty:
                            _fx_data[_label] = {"rate": float(_h["Close"].iloc[-1]), "change": 0.0, "symbol": _sym}
                    except Exception:
                        continue

            if _fx_data:
                # Display rate cards in grid
                _fx_cols = st.columns(4)
                for _i, (_pair, _info) in enumerate(_fx_data.items()):
                    _col = _fx_cols[_i % 4]
                    _chg_c = "#34d399" if _info["change"] >= 0 else "#f87171"
                    _chg_sign = "+" if _info["change"] >= 0 else ""
                    _col.markdown(f"""
                    <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:10px;
                                padding:14px;text-align:center;margin-bottom:8px;'>
                      <div style='font-size:11px;color:#5a6f8a;font-weight:600;letter-spacing:1px;'>{_pair}</div>
                      <div style='font-size:20px;font-weight:700;color:#f0f6ff;margin:4px 0;'>{_info["rate"]:.4f}</div>
                      <div style='font-size:12px;color:{_chg_c};font-weight:600;'>{_chg_sign}{_info["change"]:.2f}%</div>
                    </div>""", unsafe_allow_html=True)

                # Cross-rates matrix (EUR, USD, GBP, JPY)
                st.markdown("<div class='sec-title' style='margin-top:20px;'>Matriz de Tipos Cruzados</div>", unsafe_allow_html=True)
                _currencies = ["EUR", "USD", "GBP", "JPY"]
                # Build rates relative to USD
                _to_usd = {"USD": 1.0}
                if "EUR/USD" in _fx_data:
                    _to_usd["EUR"] = _fx_data["EUR/USD"]["rate"]
                if "GBP/USD" in _fx_data:
                    _to_usd["GBP"] = _fx_data["GBP/USD"]["rate"]
                if "USD/JPY" in _fx_data:
                    _to_usd["JPY"] = 1.0 / _fx_data["USD/JPY"]["rate"]

                _valid_ccy = [c for c in _currencies if c in _to_usd]
                if len(_valid_ccy) >= 3:
                    _matrix = []
                    for _base in _valid_ccy:
                        _row = []
                        for _quote in _valid_ccy:
                            if _base == _quote:
                                _row.append(1.0)
                            else:
                                _row.append(_to_usd[_base] / _to_usd[_quote])
                        _matrix.append(_row)

                    _fig_mx = _go_fx.Figure(data=_go_fx.Heatmap(
                        z=_matrix, x=_valid_ccy, y=_valid_ccy,
                        text=[[f"{v:.4f}" for v in r] for r in _matrix],
                        texttemplate="%{text}", textfont=dict(size=12, color="#f0f6ff"),
                        colorscale=[[0, "#0a0a0a"], [0.5, "#1e3a5f"], [1, "#60a5fa"]],
                        showscale=False,
                        hovertemplate="%{y}/%{x}: %{z:.4f}<extra></extra>",
                    ))
                    _fig_mx.update_layout(
                        paper_bgcolor="#000000", plot_bgcolor="#0a0a0a",
                        font=dict(color="#94a3b8", size=12, family="Inter"),
                        margin=dict(l=60, r=20, t=40, b=40), height=350,
                        title=dict(text="Cross Rates Matrix",
                                   font=dict(color="#94a3b8", size=13), x=0.5),
                        xaxis=dict(side="top", tickfont=dict(color="#94a3b8", size=12)),
                        yaxis=dict(tickfont=dict(color="#94a3b8", size=12)),
                    )
                    st.plotly_chart(_fig_mx, use_container_width=True)
            else:
                st.warning("No se pudieron obtener datos de divisas.")
        except Exception as _e_fx:
            st.warning(f"Error en monitor de divisas: {_e_fx}")

    # ══════════════════════════════════════════════════════════════
    # TAB 5: CALENDARIO ECONÓMICO
    # ══════════════════════════════════════════════════════════════
    with tab_cal:
        _render_economic_calendar(fred)
