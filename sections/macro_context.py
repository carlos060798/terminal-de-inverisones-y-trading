"""
sections/macro_context.py — Macro Economic Context
FRED API (free key) for yield curve, CPI, unemployment, VIX, Fed Funds Rate.
Falls back to yfinance treasury symbols if FRED key not configured.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from ui_shared import DARK, dark_layout, kpi
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
        key = st.secrets.get("FRED_API_KEY")
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

    tab_yield, tab_macro, tab_vix = st.tabs(["📈 Yield Curve", "📊 Indicadores Macro", "😰 VIX & Sentimiento"])

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
