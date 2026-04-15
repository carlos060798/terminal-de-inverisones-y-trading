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
            p_id = st.session_state.get("active_portfolio_id", 1)
            if ticker and entry > 0:
                db.add_trade(
                    trade_date=t_date, ticker=ticker.upper(), trade_type="Compra" if "Compra" in t_type else "Venta",
                    entry_price=entry, exit_price=exit_p if exit_p > 0 else None, shares=size,
                    strategy=setup, psych_notes=notes, lecciones="", errores=error_cat,
                    setup_type=setup, error_type=error_cat, trade_rating=3,
                    risk_pct=risk_p, phase=phase, event=setup,
                    abs_detected=1 if abs_det else 0, sot_detected=1 if sot_det else 0,
                    score_fortaleza=fortaleza, portfolio_id=p_id
                )
                st.success("✅ Trade guardado.")
                st.rerun()

    # 2. Análisis de KPIs
    p_id = st.session_state.get("active_portfolio_id", 1)
    trades = db.get_trades(portfolio_id=p_id)
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
    from ui_shared import fmt
    k1.markdown(kpi("P&L Total", fmt(total_pnl), f"WR: {wr:.1f}%", "green" if total_pnl >= 0 else "red"), unsafe_allow_html=True)
    k2.markdown(kpi("Win Rate", f"{wr:.0f}%", f"{len(closed)} trades", "blue"), unsafe_allow_html=True)
    k3.markdown(kpi("Riesgo Semana", f"{week_risk:.1f}%", "Límite: 8%", "orange" if week_risk < 8 else "red"), unsafe_allow_html=True)
    k4.markdown(kpi("Drawdown", f"{m_dd:.1f}%", "Límite: 15%", "green" if m_dd < 15 else "red"), unsafe_allow_html=True)

    # 3. Visualización Premium
    st.markdown("<div class='sec-title'>Atajos de Rendimiento & Análisis</div>", unsafe_allow_html=True)
    
    col_viz1, col_viz2 = st.columns([1.5, 1])
    
    with col_viz1:
        st.markdown("#### 📅 Mapa de Calor de P&L (Mensual)")
        if not closed.empty:
            # Preparar datos para el heatmap
            # Agrupar P&L por fecha
            daily_pnl = closed.groupby("trade_date")["pnl"].sum().reset_index()
            daily_pnl['trade_date'] = pd.to_datetime(daily_pnl['trade_date'])
            
            # Crear un rango de fechas para el mes actual
            today = date.today()
            start_date = today.replace(day=1)
            import calendar
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = today.replace(day=last_day)
            
            date_range = pd.date_range(start=start_date, end=end_date)
            month_df = pd.DataFrame({"trade_date": date_range})
            month_df = month_df.merge(daily_pnl, on="trade_date", how="left").fillna(0)
            
            # Formatear para heatmap (semanas vs días)
            month_df["day_of_week"] = month_df["trade_date"].dt.day_name()
            month_df["week_of_month"] = month_df["trade_date"].apply(lambda d: (d.day-1)//7 + 1)
            
            # Plotly Heatmap
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weeks = sorted(month_df["week_of_month"].unique())
            
            z = []
            text = []
            for w in weeks:
                row_z = []
                row_text = []
                for d in days:
                    val = month_df[(month_df["week_of_month"] == w) & (month_df["day_of_week"] == d)]["pnl"].values
                    dt = month_df[(month_df["week_of_month"] == w) & (month_df["day_of_week"] == d)]["trade_date"].values
                    if len(val) > 0:
                        row_z.append(val[0])
                        row_text.append(f"{pd.to_datetime(dt[0]).day}: ${val[0]:,.0f}")
                    else:
                        row_z.append(None)
                        row_text.append("")
                z.append(row_z)
                text.append(row_text)
            
            fig_hm = go.Figure(data=go.Heatmap(
                z=z, x=days, y=[f"W{w}" for w in weeks],
                colorscale=[[0, "#ef4444"], [0.5, "#1e293b"], [1, "#10b981"]],
                showscale=False,
                text=text,
                hoverinfo="text",
                xgap=3, ygap=3,
            ))
            fig_hm.update_layout(**dark_layout(height=300, margin=dict(l=10, r=10, t=10, b=10)))
            st.plotly_chart(fig_hm, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sin datos cerrados para el calendario.")

    with col_viz2:
        st.markdown("#### 🎯 Eficiencia de Ejecución")
        if not closed.empty:
            wins = len(closed[closed["pnl"] > 0])
            losses = len(closed[closed["pnl"] <= 0])
            
            fig_wr = go.Figure(data=[go.Pie(
                labels=['Wins', 'Losses'],
                values=[wins, losses],
                hole=.7,
                marker=dict(colors=['#10b981', '#ef4444']),
                textinfo='none'
            )])
            
            # Central annotation for Win Rate
            fig_wr.add_annotation(
                text=f"{wr:,.0f}%",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=30, color="white", family="Inter-Bold")
            )
            fig_wr.add_annotation(
                text="WIN RATE",
                x=0.5, y=0.35, showarrow=False,
                font=dict(size=10, color="#64748b")
            )
            
            fig_wr.update_layout(**dark_layout(height=300, showlegend=False))
            st.plotly_chart(fig_wr, use_container_width=True, config={'displayModeBar': False})

    # 4. Historial Detallado
    st.markdown("<div class='sec-title'>Bitácora de Operaciones v7</div>", unsafe_allow_html=True)
    
    # Equity Curve simplificada en expander
    with st.expander("📈 Ver Curva de Crecimiento (Equity Curve)"):
        if not closed.empty:
            trades_s = closed.sort_values("trade_date")
            trades_s["cum"] = trades_s["pnl"].cumsum()
            fig_eq = px.area(trades_s, x="trade_date", y="cum", template="plotly_dark")
            fig_eq.update_traces(line_color='#60a5fa', fillcolor='rgba(96, 165, 250, 0.1)')
            fig_eq.update_layout(**dark_layout(height=350))
            st.plotly_chart(fig_eq, use_container_width=True)
    cols_show = ["trade_date", "ticker", "trade_type", "pnl", "setup_type", "phase", "score_fortaleza", "risk_pct"]
    st.dataframe(trades[cols_show].sort_values("trade_date", ascending=False), use_container_width=True, hide_index=True)
