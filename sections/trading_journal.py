"""
sections/trading_journal.py - Diario de Trading v7 (DSD)
Sistema avanzado de registro, KPIs de riesgo y análisis post-trade.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import database as db
from ui_shared import DARK, dark_layout, kpi

# ── Configuración DSD ────────────────────────────────────────────────────────
SETUPS_DSD = ["", "Spring (Fase C)", "Upthrust (Fase C)", "Test VPOC (Cont.)", "LPS/LPSY (Fase D)", "JAC/FTI (Ruptura)", "Otro"]
ERRORS_DSD = ["", "Contra Correlación DXY", "VIX en Pánico", "Entrada Temprana (Fase B)", "Sin Confirmación", "Tamaño Excesivo", "FOMO", "Cierre Tardío (>12pm)", "Ninguno"]

def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Diario de Trading (v7)</h1>
        <p>Control del 8% Semanal · 15% Drawdown · Wyckoff Metrics</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # 1. Registro de Operación
    with st.expander("➕ Registrar Nueva Operación v7", expanded=False):
        # Intentar recuperar datos del último análisis del Engine
        default_analysis = st.session_state.get("last_v7_analysis", {})
        
        c1, c2, c3 = st.columns(3)
        t_date = c1.date_input("📅 Fecha", value=date.today())
        ticker = c2.text_input("Activo / Ticker", placeholder="ES, EURUSD, BTC...")
        t_type = c3.selectbox("Dirección", ["Compra (Long)", "Venta (Short)"])

        c4, c5, c6 = st.columns(3)
        entry = c4.number_input("Entrada", min_value=0.0, step=0.0001, format="%.5f")
        exit_p = c5.number_input("Salida (0 si abierta)", min_value=0.0, step=0.0001, format="%.5f")
        size = c6.number_input("Tamaño (Lotes/Contratos)", min_value=0.0, step=0.01)

        st.markdown("---")
        st.markdown("#### Configuración Wyckoff v7")
        w1, w2, w3 = st.columns(3)
        setup = w1.selectbox("Setup Wyckoff", SETUPS_DSD, index=SETUPS_DSD.index(default_analysis.get("event", "")) if default_analysis.get("event") in SETUPS_DSD else 0)
        phase = w2.selectbox("Fase", ["", "A", "B", "C", "D", "E"], index=["", "A", "B", "C", "D", "E"].index(default_analysis.get("phase", "")) if default_analysis.get("phase") in ["", "A", "B", "C", "D", "E"] else 0)
        fortaleza = w3.slider("Fortaleza (%)", 0, 100, default_analysis.get("fortaleza", 50))

        w4, w5, w6 = st.columns(3)
        abs_det = w4.checkbox("Absorción ✓")
        sot_det = w5.checkbox("SOT ✓")
        risk_p = w6.number_input("Riesgo %", value=2.0, step=0.1)

        st.markdown("---")
        notes = st.text_area("Psicología & Notas")
        error_cat = st.selectbox("Categoría de Error", ERRORS_DSD)

        if st.button("💾 Registrar Trade", type="primary"):
            if ticker and entry > 0:
                db.add_trade(
                    trade_date=t_date, ticker=ticker.upper(), trade_type="Compra" if "Compra" in t_type else "Venta",
                    entry_price=entry, exit_price=exit_p if exit_p > 0 else None, shares=size,
                    strategy=setup, psych_notes=notes, lecciones="", errores=error_cat,
                    setup_type=setup, error_type=error_cat, trade_rating=3,
                    risk_pct=risk_p, phase=phase, event=setup,
                    abs_detected=1 if abs_det else 0, sot_detected=1 if sot_det else 0,
                    score_fortaleza=fortaleza
                )
                st.success("✅ Trade guardado.")
                st.rerun()

    # 2. Análisis de KPIs
    trades = db.get_trades()
    if trades.empty:
        st.info("No hay datos para analizar.")
        return

    closed = trades[trades["pnl"].notna()]
    total_pnl = closed["pnl"].sum()
    wr = (len(closed[closed["pnl"] > 0]) / len(closed) * 100) if not closed.empty else 0
    
    # Riesgo Semanal (8%)
    curr_week = datetime.now().isocalendar()[1]
    trades["week"] = pd.to_datetime(trades["trade_date"]).dt.isocalendar().week
    week_risk = trades[trades["week"] == curr_week]["risk_pct"].sum()
    
    # Drawdown (15%)
    eq = closed.sort_values("trade_date")["pnl"].cumsum()
    peak = eq.cummax()
    dd = (eq - peak) / peak.replace(0, 1) * 100
    m_dd = abs(dd.min()) if not dd.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi("P&L Total", f"${total_pnl:,.2f}", f"WR: {wr:.1f}%", "green" if total_pnl >= 0 else "red"), unsafe_allow_html=True)
    k2.markdown(kpi("Win Rate", f"{wr:.0f}%", f"{len(closed)} trades", "blue"), unsafe_allow_html=True)
    k3.markdown(kpi("Riesgo Semana", f"{week_risk:.1f}%", "Límite: 8%", "orange" if week_risk < 8 else "red"), unsafe_allow_html=True)
    k4.markdown(kpi("Drawdown", f"{m_dd:.1f}%", "Límite: 15%", "green" if m_dd < 15 else "red"), unsafe_allow_html=True)

    # 3. Visualización
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("#### Equity Curve (Cierre)")
        if not closed.empty:
            trades_s = closed.sort_values("trade_date")
            trades_s["cum"] = trades_s["pnl"].cumsum()
            fig = px.line(trades_s, x="trade_date", y="cum", markers=True, template="plotly_dark")
            fig.update_layout(**dark_layout(height=400))
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### Fortaleza vs Resultado")
        if not closed.empty and "score_fortaleza" in closed.columns:
            fig_f = px.scatter(closed, x="score_fortaleza", y="pnl", color="pnl", 
                             color_continuous_scale="RdYlGn", size=closed["pnl"].abs().fillna(1),
                             template="plotly_dark")
            fig_f.update_layout(**dark_layout(height=400, showlegend=False))
            st.plotly_chart(fig_f, use_container_width=True)

    # 4. Tabla Detallada
    st.markdown("---")
    st.markdown("#### Historial DSD v7")
    cols_show = ["trade_date", "ticker", "trade_type", "pnl", "setup_type", "phase", "score_fortaleza", "risk_pct"]
    st.dataframe(trades[cols_show].sort_values("trade_date", ascending=False), use_container_width=True, hide_index=True)
