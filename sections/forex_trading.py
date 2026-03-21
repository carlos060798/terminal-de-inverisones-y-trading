"""
sections/forex_trading.py - Forex & Indices Trading Journal
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import database as db
from ui_shared import DARK, kpi


FOREX_PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD",
    "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY", "EUR/AUD", "EUR/CHF",
]
INDICES = [
    "US500", "US30", "US100", "GER40", "UK100", "JPN225", "FRA40",
    "SPX", "NDX", "DJI", "FTSE", "DAX", "NIKKEI",
]
COMMODITIES = ["XAUUSD", "XAGUSD", "USOIL", "UKOIL", "NATGAS", "COPPER"]
CRYPTO = ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD"]

TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN"]
SESSIONS = ["", "Asia", "London", "New York", "London/NY Overlap"]
STRATEGIES_FX = [
    "", "Scalping", "Day Trading", "Swing Trading", "Breakout",
    "Trend Following", "Mean Reversion", "News Trading",
    "Supply & Demand", "ICT/SMC", "Price Action", "Otra",
]


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Trading Forex & Indices</h1>
        <p>Registro de operaciones · Pips · Lotes · Sesiones · Gestión de riesgo</p>
      </div>
    </div>""", unsafe_allow_html=True)

    with st.expander("➕  Nueva operación", expanded=True):
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        td = r1c1.date_input("Fecha", value=date.today(), key="fx_date")

        inst_type = r1c2.selectbox("Tipo", ["Forex", "Índice", "Commodities", "Crypto"], key="fx_type")
        if inst_type == "Forex":
            instruments = FOREX_PAIRS
        elif inst_type == "Índice":
            instruments = INDICES
        elif inst_type == "Commodities":
            instruments = COMMODITIES
        else:
            instruments = CRYPTO

        instrument = r1c3.selectbox("Instrumento", [""] + instruments + ["Otro…"], key="fx_inst")
        if instrument == "Otro…":
            instrument = r1c3.text_input("Instrumento personalizado", key="fx_custom")

        direction = r1c4.selectbox("Dirección", ["Buy (Long)", "Sell (Short)"], key="fx_dir")

        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        lots = r2c1.number_input("Lotes", min_value=0.0, step=0.01, format="%.2f", key="fx_lots")
        entry = r2c2.number_input("Precio entrada", min_value=0.0, step=0.0001, format="%.5f", key="fx_entry")
        exit_p = r2c3.number_input("Precio salida (0=abierta)", min_value=0.0, step=0.0001, format="%.5f", key="fx_exit")
        pips_input = r2c4.number_input("Pips (auto si salida)", step=0.1, format="%.1f", key="fx_pips")

        r3c1, r3c2, r3c3, r3c4 = st.columns(4)
        sl = r3c1.number_input("Stop Loss", min_value=0.0, step=0.0001, format="%.5f", key="fx_sl")
        tp = r3c2.number_input("Take Profit", min_value=0.0, step=0.0001, format="%.5f", key="fx_tp")
        commission = r3c3.number_input("Comisión ($)", min_value=0.0, step=0.1, format="%.2f", key="fx_comm")
        swap = r3c4.number_input("Swap ($)", step=0.01, format="%.2f", key="fx_swap")

        r4c1, r4c2, r4c3 = st.columns(3)
        strategy = r4c1.selectbox("Estrategia", STRATEGIES_FX, key="fx_strat")
        timeframe = r4c2.selectbox("Timeframe", [""] + TIMEFRAMES, key="fx_tf")
        session = r4c3.selectbox("Sesión", SESSIONS, key="fx_sess")

        notes = st.text_area("Notas de la operación",
                             placeholder="Setup, confluencias, gestión emocional…",
                             height=70, key="fx_notes")

        if st.button("Registrar operación", key="fx_submit"):
            if instrument and entry > 0 and lots > 0:
                # Auto-calculate pips if exit price given
                pips = pips_input
                pnl = None
                if exit_p > 0 and entry > 0:
                    is_buy = "Buy" in direction
                    # Pip calculation (forex pairs with JPY have different pip size)
                    if "JPY" in instrument:
                        pip_size = 0.01
                    else:
                        pip_size = 0.0001

                    if is_buy:
                        pips = (exit_p - entry) / pip_size
                    else:
                        pips = (entry - exit_p) / pip_size

                    # Approximate P&L: pips * lot_value * lots
                    # Standard lot = 100,000 units, pip value ~$10 for major pairs
                    pip_value = 10.0 if "JPY" not in instrument else 1000.0 / entry if entry > 0 else 10.0
                    if inst_type != "Forex":
                        pip_value = lots  # For indices/commodities, use contract value
                        pips = exit_p - entry if is_buy else entry - exit_p

                    pnl = (pips * pip_value * lots) - commission + swap

                db.add_forex_trade(
                    td, instrument, inst_type.lower(), direction,
                    lots, entry, exit_p if exit_p > 0 else None,
                    sl if sl > 0 else None, tp if tp > 0 else None,
                    pips, pnl, commission, swap, strategy, timeframe, session, notes
                )
                st.success("Operación registrada.")
                st.rerun()
            else:
                st.warning("Completa Instrumento, Precio de Entrada y Lotes.")

    # ── TRADES DATA ──
    trades = db.get_forex_trades()
    if trades.empty:
        st.info("Aún no hay operaciones de Forex/Índices registradas.")
        return

    closed = trades[trades["pnl"].notna()]
    wins = closed[closed["pnl"] > 0]
    losses = closed[closed["pnl"] <= 0]
    wr = len(wins) / len(closed) * 100 if len(closed) > 0 else 0
    pf = abs(wins["pnl"].sum() / losses["pnl"].sum()) if not losses.empty and losses["pnl"].sum() != 0 else 0
    tp_total = closed["pnl"].sum() if not closed.empty else 0
    avg_pips = closed["pips"].mean() if not closed.empty and "pips" in closed.columns else 0

    # ── KPIs ──
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi("Win Rate", f"{wr:.1f}%",
                     f"{len(wins)}W / {len(losses)}L",
                     "green" if wr >= 50 else "red"), unsafe_allow_html=True)
    k2.markdown(kpi("Factor Beneficio", f"{pf:.2f}x",
                     "≥ 1.5 ideal",
                     "green" if pf >= 1 else "red"), unsafe_allow_html=True)
    k3.markdown(kpi("P&L Total", f"${tp_total:,.0f}",
                     f"{len(closed)} cerradas",
                     "green" if tp_total >= 0 else "red"), unsafe_allow_html=True)
    k4.markdown(kpi("Avg Pips", f"{avg_pips:+.1f}",
                     f"{closed['pips'].sum():.0f} pips totales" if not closed.empty else "",
                     "green" if avg_pips > 0 else "red"), unsafe_allow_html=True)

    # ── EQUITY CURVE ──
    st.markdown("<div class='sec-title'>Curva de Equity</div>", unsafe_allow_html=True)
    eq = closed.sort_values("trade_date").copy()
    eq["cum"] = eq["pnl"].cumsum()
    eq["color"] = eq["pnl"].apply(lambda x: "#34d399" if x >= 0 else "#f87171")

    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=eq["trade_date"], y=eq["cum"],
        mode="lines", name="Equity",
        line=dict(color="#60a5fa", width=2.5),
        fill="tozeroy", fillcolor="rgba(96,165,250,0.08)"))
    fig_eq.add_trace(go.Bar(x=eq["trade_date"], y=eq["pnl"],
        marker_color=eq["color"], name="P&L", opacity=0.6, yaxis="y2"))
    fig_eq.add_hline(y=0, line_dash="dot", line_color="#334155")
    fig_eq.update_layout(**DARK, height=300,
        yaxis=dict(title="P&L Acumulado", gridcolor="#1e2d40"),
        yaxis2=dict(title="P&L Trade", overlaying="y", side="right", showgrid=False),
        legend=dict(bgcolor="#0f1923", bordercolor="#1e2d40", font=dict(size=11)))
    st.plotly_chart(fig_eq, use_container_width=True)

    # ── ANALYTICS ──
    st.markdown("<div class='sec-title'>Análisis de Desempeño</div>", unsafe_allow_html=True)
    ch1, ch2, ch3 = st.columns(3)

    with ch1:
        # P&L by instrument
        by_inst = closed.groupby("instrument")["pnl"].sum().reset_index().sort_values("pnl", ascending=False)
        if not by_inst.empty:
            fig_inst = go.Figure(go.Bar(
                x=by_inst["instrument"], y=by_inst["pnl"],
                marker_color=["#34d399" if v >= 0 else "#f87171" for v in by_inst["pnl"]],
                text=[f"${v:+,.0f}" for v in by_inst["pnl"]], textposition="outside",
                textfont=dict(color="#94a3b8", size=10)))
            fig_inst.update_layout(**DARK, height=260,
                title=dict(text="P&L por Instrumento", font=dict(color="#94a3b8", size=13), x=0.5),
                showlegend=False)
            st.plotly_chart(fig_inst, use_container_width=True)

    with ch2:
        # P&L by session
        by_sess = closed[closed["session"] != ""].groupby("session")["pnl"].agg(["sum", "count"]).reset_index()
        if not by_sess.empty:
            fig_sess = go.Figure(go.Bar(
                x=by_sess["session"], y=by_sess["sum"],
                marker_color=["#60a5fa", "#a78bfa", "#fbbf24", "#34d399"][:len(by_sess)],
                text=[f"${v:+,.0f}" for v in by_sess["sum"]], textposition="outside",
                textfont=dict(color="#94a3b8", size=10)))
            fig_sess.update_layout(**DARK, height=260,
                title=dict(text="P&L por Sesión", font=dict(color="#94a3b8", size=13), x=0.5),
                showlegend=False)
            st.plotly_chart(fig_sess, use_container_width=True)

    with ch3:
        # P&L by strategy
        by_strat = closed[closed["strategy"] != ""].groupby("strategy")["pnl"].agg(["sum", "count"]).reset_index()
        if not by_strat.empty:
            fig_strat = go.Figure(go.Bar(
                x=by_strat["strategy"], y=by_strat["sum"],
                marker_color=["#34d399" if v >= 0 else "#f87171" for v in by_strat["sum"]],
                text=[f"${v:+,.0f} ({n})" for v, n in zip(by_strat["sum"], by_strat["count"])],
                textposition="outside", textfont=dict(color="#94a3b8", size=10)))
            fig_strat.update_layout(**DARK, height=260,
                title=dict(text="P&L por Estrategia", font=dict(color="#94a3b8", size=13), x=0.5),
                showlegend=False)
            st.plotly_chart(fig_strat, use_container_width=True)

    # ── TRADE LOG ──
    st.markdown("<div class='sec-title'>Historial de Operaciones</div>", unsafe_allow_html=True)
    show_cols = ["trade_date", "instrument", "instrument_type", "direction", "lots",
                 "entry_price", "exit_price", "pips", "pnl", "strategy", "timeframe", "session"]
    show = trades[[c for c in show_cols if c in trades.columns]].copy()
    show.columns = ["Fecha", "Instrumento", "Tipo", "Dir.", "Lotes",
                    "Entrada", "Salida", "Pips", "P&L $", "Estrategia", "TF", "Sesión"][:len(show.columns)]

    def clr_pnl(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "color:#475569"
        return "color:#34d399" if v >= 0 else "color:#f87171"

    st.dataframe(
        show.style.applymap(clr_pnl, subset=["Pips", "P&L $"])
                 .format({"Entrada": "{:.5f}", "Salida": "{:.5f}",
                          "Pips": "{:+.1f}", "P&L $": "${:+,.2f}", "Lotes": "{:.2f}"},
                          na_rep="Abierta"),
        use_container_width=True, hide_index=True
    )

    with st.expander("Eliminar operación por ID"):
        del_id = st.number_input("ID", min_value=1, step=1, key="fx_del_id", label_visibility="collapsed")
        if st.button("Eliminar", key="fx_del_btn"):
            db.delete_forex_trade(int(del_id))
            st.success(f"Operación #{del_id} eliminada.")
            st.rerun()
