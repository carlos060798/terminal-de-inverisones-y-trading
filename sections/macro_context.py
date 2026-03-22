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

    st.markdown("### Calendario Econ\u00f3mico 2026")
    st.markdown("Eventos macro que mueven los mercados")

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
                    fig = go.Figure(go.Scatter(
                        x=hist.index, y=hist.values, mode="lines",
                        line=dict(color="#3b82f6", width=2)
                    ))
                    fig.update_layout(**dark_layout(
                        height=300,
                        title=dict(
                            text=f"{series_id} \u2014 \u00daltimos 3 a\u00f1os",
                            font=dict(color="#94a3b8")
                        )
                    ))
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.warning(f"No se pudo cargar {series_id}: {e}")
    elif not fred:
        st.info("Conecta tu API key de FRED para ver series hist\u00f3ricas de cada evento.")


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

    tab_yield, tab_macro, tab_vix, tab_fx, tab_cal = st.tabs(["📈 Yield Curve", "📊 Indicadores Macro", "😰 VIX & Sentimiento", "💱 Monitor de Divisas", "📅 Calendario Económico"])

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

            # Yield curve chart
            fig_yc = go.Figure()
            labels = list(yc_data.keys())
            values = list(yc_data.values())
            fig_yc.add_trace(go.Scatter(
                x=labels, y=values, mode="lines+markers",
                line=dict(color="#60a5fa", width=3),
                marker=dict(size=10, color="#60a5fa"),
                fill="tozeroy", fillcolor="rgba(96,165,250,0.08)",
                text=[f"{v:.2f}%" for v in values],
                textposition="top center",
                textfont=dict(color="#94a3b8", size=11),
            ))
            fig_yc.update_layout(**DARK, height=400,
                title=dict(text="Curva de Rendimiento del Tesoro de EE.UU.",
                          font=dict(color="#94a3b8", size=14), x=0.5),
                yaxis_title="Rendimiento (%)",
                xaxis_title="Plazo",
                showlegend=False)
            st.plotly_chart(fig_yc, use_container_width=True)

            # Historical 10Y if FRED
            if using_fred:
                try:
                    hist_10y = fred.get_series("GS10", observation_start=datetime.now() - timedelta(days=365*2))
                    if not hist_10y.empty:
                        fig_10y = go.Figure()
                        fig_10y.add_trace(go.Scatter(
                            x=hist_10y.index, y=hist_10y.values,
                            mode="lines", line=dict(color="#a78bfa", width=1.5),
                            fill="tozeroy", fillcolor="rgba(167,139,250,0.06)",
                        ))
                        fig_10y.update_layout(**DARK, height=280,
                            title=dict(text="Treasury 10Y — Últimos 2 años",
                                      font=dict(color="#94a3b8", size=13), x=0.5),
                            yaxis_title="%", showlegend=False)
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
            with st.spinner("Cargando indicadores macro…"):
                macro_series = {
                    "CPI (Inflación)": ("CPIAUCSL", "Índice de Precios al Consumidor", "#f87171"),
                    "Desempleo": ("UNRATE", "Tasa de Desempleo (%)", "#fbbf24"),
                    "Fed Funds Rate": ("FEDFUNDS", "Tasa de Fondos Federales (%)", "#60a5fa"),
                }

                # KPIs row
                mk1, mk2, mk3 = st.columns(3)
                kpi_cols = [mk1, mk2, mk3]

                for i, (name, (series_id, desc, color)) in enumerate(macro_series.items()):
                    try:
                        data = fred.get_series(series_id,
                                              observation_start=datetime.now() - timedelta(days=365*3))
                        if not data.empty:
                            latest = data.dropna().iloc[-1]
                            prev_year = data.dropna().iloc[-13] if len(data) > 13 else latest

                            if series_id == "CPIAUCSL":
                                # CPI: show YoY % change
                                yoy = ((latest - prev_year) / prev_year) * 100
                                kpi_cols[i].markdown(kpi(name, f"{yoy:.1f}%",
                                    "YoY" + (" ↓" if yoy < 3 else " ↑"), "green" if yoy < 3 else "red"),
                                    unsafe_allow_html=True)
                            else:
                                kpi_cols[i].markdown(kpi(name, f"{latest:.2f}%", desc[:20],
                                    "blue"), unsafe_allow_html=True)

                            # Chart
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=data.index, y=data.values,
                                mode="lines", line=dict(color=color, width=1.5),
                                fill="tozeroy", fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.06)",
                            ))
                            fig.update_layout(**dark_layout(height=250,
                                title=dict(text=f"{name} — 3 años",
                                          font=dict(color="#94a3b8", size=12), x=0.5),
                                showlegend=False, margin=dict(l=40, r=20, t=40, b=30)))
                            st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Error cargando {name}: {e}")
        else:
            st.info("Los indicadores macro detallados (CPI, desempleo, Fed Funds) requieren una API key de FRED (gratis).")
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
                if st.button("🧠 Insight Macro con IA"):
                    with st.spinner("Generando insight macro…"):
                        ai_result = ai_engine.generate_macro_insight(
                            vix=vix_current,
                            sp500_ytd=sp_ytd,
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
