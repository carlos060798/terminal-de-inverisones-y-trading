"""
sections/dashboard.py - Dashboard Overview / Home page
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import database as db
from ui_shared import DARK, fmt, kpi

try:
    import yfinance as yf
except ImportError:
    yf = None


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Dashboard</h1>
        <p>Resumen ejecutivo · Cartera · Trading · Análisis recientes</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── PORTFOLIO SUMMARY ──
    wl = db.get_watchlist()
    trades_stock = db.get_trades()
    trades_fx = db.get_forex_trades()
    analyses = db.get_stock_analyses()

    # Portfolio value
    total_val = 0
    total_inv = 0
    total_pnl_portfolio = 0
    positions = 0
    if not wl.empty and yf:
        positions = len(wl)
        for _, row in wl.iterrows():
            try:
                price = yf.Ticker(row["ticker"]).fast_info.last_price or 0
                val = row["shares"] * price
                inv = row["shares"] * row["avg_cost"]
                total_val += val
                total_inv += inv
            except:
                total_inv += row["shares"] * row["avg_cost"]

        total_pnl_portfolio = total_val - total_inv

    # Trading P&L
    stock_pnl = trades_stock[trades_stock["pnl"].notna()]["pnl"].sum() if not trades_stock.empty else 0
    fx_pnl = trades_fx[trades_fx["pnl"].notna()]["pnl"].sum() if not trades_fx.empty else 0
    total_trading_pnl = stock_pnl + fx_pnl

    # ── TOP KPIs ──
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(kpi("Valor Cartera", fmt(total_val) if total_val > 0 else "$0",
                     f"{positions} posiciones", "blue"), unsafe_allow_html=True)

    pnl_color = "green" if total_pnl_portfolio >= 0 else "red"
    pct = (total_pnl_portfolio / total_inv * 100) if total_inv > 0 else 0
    k2.markdown(kpi("P&L Cartera", fmt(total_pnl_portfolio),
                     f"{pct:+.2f}%", pnl_color), unsafe_allow_html=True)

    k3.markdown(kpi("P&L Trading", f"${total_trading_pnl:+,.0f}",
                     f"Acciones: ${stock_pnl:+,.0f} | Forex: ${fx_pnl:+,.0f}",
                     "green" if total_trading_pnl >= 0 else "red"), unsafe_allow_html=True)

    n_trades = len(trades_stock) + len(trades_fx)
    k4.markdown(kpi("Total Trades", str(n_trades),
                     f"Acciones: {len(trades_stock)} | Forex: {len(trades_fx)}",
                     "blue"), unsafe_allow_html=True)

    k5.markdown(kpi("Análisis PDF", str(len(analyses)),
                     f"{len(db.get_analyzed_tickers())} tickers",
                     "purple"), unsafe_allow_html=True)

    # ── RECENT ACTIVITY ──
    st.markdown("<div class='sec-title'>Actividad Reciente</div>", unsafe_allow_html=True)

    act1, act2 = st.columns(2)

    with act1:
        st.markdown("**Últimos análisis**")
        if not analyses.empty:
            recent = analyses.head(5)[["ticker", "company_name", "price", "pe_ratio", "analyzed_at"]].copy()
            recent.columns = ["Ticker", "Empresa", "Precio", "P/E", "Fecha"]
            st.dataframe(recent, use_container_width=True, hide_index=True)
        else:
            st.info("Sin análisis aún.")

    with act2:
        st.markdown("**Últimas operaciones**")
        all_trades = []
        if not trades_stock.empty:
            for _, t in trades_stock.head(3).iterrows():
                all_trades.append({
                    "Fecha": t["trade_date"], "Tipo": "Acción",
                    "Instrumento": t["ticker"], "P&L": t.get("pnl"),
                })
        if not trades_fx.empty:
            for _, t in trades_fx.head(3).iterrows():
                all_trades.append({
                    "Fecha": t["trade_date"], "Tipo": t.get("instrument_type", "forex").title(),
                    "Instrumento": t["instrument"], "P&L": t.get("pnl"),
                })
        if all_trades:
            rt_df = pd.DataFrame(all_trades).sort_values("Fecha", ascending=False).head(5)
            st.dataframe(rt_df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin operaciones aún.")

    # ── CHARTS ──
    if not trades_stock.empty or not trades_fx.empty:
        st.markdown("<div class='sec-title'>Performance Global</div>", unsafe_allow_html=True)
        gc1, gc2 = st.columns(2)

        with gc1:
            # Combined equity curve
            all_pnl = []
            if not trades_stock.empty:
                closed_s = trades_stock[trades_stock["pnl"].notna()].copy()
                if not closed_s.empty:
                    for _, t in closed_s.iterrows():
                        all_pnl.append({"date": t["trade_date"], "pnl": t["pnl"], "type": "Acciones"})
            if not trades_fx.empty:
                closed_f = trades_fx[trades_fx["pnl"].notna()].copy()
                if not closed_f.empty:
                    for _, t in closed_f.iterrows():
                        all_pnl.append({"date": t["trade_date"], "pnl": t["pnl"], "type": "Forex"})

            if all_pnl:
                eq_df = pd.DataFrame(all_pnl).sort_values("date")
                eq_df["cum"] = eq_df["pnl"].cumsum()

                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(
                    x=eq_df["date"], y=eq_df["cum"],
                    mode="lines", name="Equity Total",
                    line=dict(color="#60a5fa", width=2.5),
                    fill="tozeroy", fillcolor="rgba(96,165,250,0.08)"))
                fig_eq.add_hline(y=0, line_dash="dot", line_color="#334155")
                fig_eq.update_layout(**DARK, height=300,
                    title=dict(text="Equity Curve Global", font=dict(color="#94a3b8", size=13), x=0.5),
                    legend=dict(bgcolor="#0f1923", bordercolor="#1e2d40"))
                st.plotly_chart(fig_eq, use_container_width=True)

        with gc2:
            # P&L by type pie
            pnl_data = []
            if stock_pnl != 0:
                pnl_data.append({"Tipo": "Acciones", "P&L": abs(stock_pnl), "Real": stock_pnl})
            if fx_pnl != 0:
                pnl_data.append({"Tipo": "Forex/Índices", "P&L": abs(fx_pnl), "Real": fx_pnl})
            if total_pnl_portfolio != 0:
                pnl_data.append({"Tipo": "Cartera (no realizado)", "P&L": abs(total_pnl_portfolio), "Real": total_pnl_portfolio})

            if pnl_data:
                pnl_pie = pd.DataFrame(pnl_data)
                colors = ["#60a5fa", "#a78bfa", "#fbbf24"]
                fig_pie = go.Figure(go.Pie(
                    labels=pnl_pie["Tipo"], values=pnl_pie["P&L"],
                    marker_colors=colors[:len(pnl_pie)], hole=0.55,
                    textfont=dict(color="white"),
                    textinfo="label+percent"))
                fig_pie.update_layout(**DARK, height=300,
                    title=dict(text="Distribución P&L", font=dict(color="#94a3b8", size=13), x=0.5),
                    showlegend=False,
                    annotations=[dict(text=f"${total_trading_pnl + total_pnl_portfolio:+,.0f}",
                        x=0.5, y=0.5, showarrow=False,
                        font=dict(size=18, color="#f0f6ff", family="Inter"))])
                st.plotly_chart(fig_pie, use_container_width=True)

    # ── INVESTMENT THESES SUMMARY ──
    theses = db.get_all_investment_notes()
    if not theses.empty:
        st.markdown("<div class='sec-title'>Tesis de Inversión</div>", unsafe_allow_html=True)
        thesis_show = theses[["ticker", "moat_type", "moat_rating", "thesis_verdict", "updated_at"]].copy()
        thesis_show.columns = ["Ticker", "MOAT", "Rating", "Veredicto", "Actualizado"]

        def verdict_color(v):
            if v == "Comprar":
                return "color:#34d399"
            elif v == "Evitar":
                return "color:#f87171"
            elif v == "Mantener":
                return "color:#fbbf24"
            return "color:#475569"

        st.dataframe(
            thesis_show.style.applymap(verdict_color, subset=["Veredicto"]),
            use_container_width=True, hide_index=True
        )
