"""
pages/trading_journal.py - Trading Journal section
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import database as db
from ui_shared import DARK, kpi
import excel_export
import ai_engine


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Diario de Trading</h1>
        <p>Registro de operaciones · P&L automático · Estadísticas de desempeño</p>
      </div>
    </div>""", unsafe_allow_html=True)

    with st.expander("➕  Registrar nueva operación", expanded=True):
        r1c1,r1c2,r1c3 = st.columns(3)
        td  = r1c1.date_input("📅 Fecha", value=date.today())
        ttk = r1c2.text_input("Ticker", placeholder="AAPL")
        tty = r1c3.selectbox("Tipo", ["Compra","Venta"])
        r2c1,r2c2,r2c3 = st.columns(3)
        ep  = r2c1.number_input("Entrada ($)", min_value=0.0, step=0.01, format="%.4f")
        xp  = r2c2.number_input("Salida ($) — 0 si abierta", min_value=0.0, step=0.01, format="%.4f")
        sh  = r2c3.number_input("Acciones", min_value=0.0, step=1.0)
        st_g = st.selectbox("Estrategia", ["","Momentum","Value Investing","Swing Trading",
                                            "Scalping","Breakout","Reversión a la media","GARP","Otra"])
        pn  = st.text_area("🧠 Notas Psicológicas",
                           placeholder="¿Seguiste el plan? ¿FOMO? ¿Entraste con convicción o con miedo?",
                           height=80)
        lecc = st.text_area("📚 Lecciones Aprendidas",
                            placeholder="¿Qué aprendiste de esta operación?",
                            height=80)
        errs = st.text_area("⚠️ Errores Cometidos",
                            placeholder="¿Qué harías diferente?",
                            height=80)
        if st.button("📝  Registrar operación"):
            if ttk.strip() and ep > 0 and sh > 0:
                db.add_trade(td, ttk.strip(), tty, ep, xp if xp > 0 else None, sh, st_g, pn,
                             lecc, errs)
                st.success("✅ Operación registrada."); st.rerun()
            else:
                st.warning("Completa Ticker, Precio de Entrada y Acciones.")

    trades = db.get_trades()
    if trades.empty:
        st.info("Aún no hay operaciones registradas.")
    else:
        closed = trades[trades["pnl"].notna()]
        wins   = closed[closed["pnl"] > 0]
        losses = closed[closed["pnl"] <= 0]
        wr     = len(wins) / len(closed) * 100 if len(closed) > 0 else 0
        pf     = abs(wins["pnl"].sum() / losses["pnl"].sum()) if not losses.empty and losses["pnl"].sum() != 0 else 0
        tp     = closed["pnl"].sum() if not closed.empty else 0
        avg_w  = wins["pnl"].mean()   if not wins.empty   else 0
        avg_l  = losses["pnl"].mean() if not losses.empty else 0

        # ── KPIs ──
        k1,k2,k3,k4 = st.columns(4)
        wr_color = "green" if wr >= 50 else "red"
        pf_color = "green" if pf >= 1  else "red"
        tp_color = "green" if tp >= 0  else "red"
        k1.markdown(kpi("🎯 Win Rate",        f"{wr:.1f}%",    f"{len(wins)}W / {len(losses)}L", wr_color), unsafe_allow_html=True)
        k2.markdown(kpi("⚡ Factor Beneficio", f"{pf:.2f}x",   "≥ 1.5 ideal",                   pf_color), unsafe_allow_html=True)
        k3.markdown(kpi("💰 P&L Total",        f"${tp:,.0f}",  f"{len(closed)} cerradas",        tp_color), unsafe_allow_html=True)
        k4.markdown(kpi("📊 Ratio R:R",
                         f"{abs(avg_w/avg_l):.2f}x" if avg_l != 0 else "—",
                         f"Avg W: ${avg_w:,.0f} / Avg L: ${avg_l:,.0f}", "blue"),
                    unsafe_allow_html=True)

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
            marker_color=eq["color"], name="P&L por trade", opacity=0.6,
            yaxis="y2"))
        fig_eq.add_hline(y=0, line_dash="dot", line_color="#334155")
        fig_eq.update_layout(**DARK, height=300,
            yaxis=dict(title="P&L Acumulado", gridcolor="#1e2d40"),
            yaxis2=dict(title="P&L Trade", overlaying="y", side="right", showgrid=False),
            legend=dict(bgcolor="#0f1923", bordercolor="#1e2d40", font=dict(size=11)))
        st.plotly_chart(fig_eq, use_container_width=True)

        st.markdown("<div class='sec-title'>Análisis de Desempeño</div>", unsafe_allow_html=True)
        ch1, ch2, ch3 = st.columns(3)

        with ch1:
            fig_wl = go.Figure(go.Pie(
                labels=["Ganadoras","Perdedoras"],
                values=[len(wins), len(losses)],
                marker_colors=["#34d399","#f87171"], hole=0.55,
                textfont=dict(color="white")))
            fig_wl.update_layout(**DARK, height=260,
                title=dict(text="Win / Loss", font=dict(color="#94a3b8",size=13), x=0.5),
                showlegend=False,
                annotations=[dict(text=f"{wr:.0f}%", x=0.5, y=0.5, showarrow=False,
                    font=dict(size=22, color="#f0f6ff", family="Inter"))])
            st.plotly_chart(fig_wl, use_container_width=True)

        with ch2:
            tk_pnl = closed.groupby("ticker")["pnl"].sum().reset_index().sort_values("pnl", ascending=False)
            fig_tk = go.Figure(go.Bar(
                x=tk_pnl["ticker"], y=tk_pnl["pnl"],
                marker_color=["#34d399" if v >= 0 else "#f87171" for v in tk_pnl["pnl"]],
                text=[f"${v:+,.0f}" for v in tk_pnl["pnl"]], textposition="outside",
                textfont=dict(color="#94a3b8", size=10)))
            fig_tk.update_layout(**DARK, height=260,
                title=dict(text="P&L por Ticker", font=dict(color="#94a3b8",size=13), x=0.5),
                showlegend=False)
            st.plotly_chart(fig_tk, use_container_width=True)

        with ch3:
            fig_dist = px.histogram(closed, x="pnl", nbins=15,
                color_discrete_sequence=["#60a5fa"])
            fig_dist.add_vline(x=0, line_dash="dot", line_color="#f87171")
            fig_dist.update_layout(**DARK, height=260,
                title=dict(text="Distribución P&L", font=dict(color="#94a3b8",size=13), x=0.5),
                xaxis_title="P&L ($)", yaxis_title="# Trades", showlegend=False)
            st.plotly_chart(fig_dist, use_container_width=True)

        st.markdown("<div class='sec-title'>Historial de Operaciones</div>", unsafe_allow_html=True)
        show = trades[["trade_date","ticker","trade_type","entry_price","exit_price",
                        "shares","pnl","pnl_pct","strategy","psych_notes",
                        "lecciones","errores"]].copy()
        show.columns = ["Fecha","Ticker","Tipo","Entrada $","Salida $",
                        "Acciones","P&L $","P&L %","Estrategia","Notas",
                        "Lecciones Aprendidas","Errores Cometidos"]
        st.dataframe(
            show.style.map(lambda v: "color:#34d399" if isinstance(v,(int,float)) and not pd.isna(v) and v>0
                                else ("color:#f87171" if isinstance(v,(int,float)) and not pd.isna(v) and v<0
                                else "color:#475569"), subset=["P&L $","P&L %"])
                     .format({"Entrada $":"${:.4f}","Salida $":"${:.4f}",
                              "P&L $":"${:+,.2f}","P&L %":"{:+.2f}%","Acciones":"{:.2f}"},
                              na_rep="Abierta"),
            use_container_width=True, hide_index=True
        )
        # ── AI TRADE ANALYSIS ──
        providers = ai_engine.get_available_providers()
        if providers and not closed.empty:
            with st.expander("🧠 Análisis IA de Trading"):
                last_trade = closed.iloc[-1]
                st.markdown(f"**Última operación cerrada:** {last_trade['ticker']} — P&L: ${last_trade['pnl']:+,.2f}")
                if st.button("Analizar última operación con IA"):
                    with st.spinner("Analizando…"):
                        ai_result = ai_engine.analyze_trade(
                            ticker=last_trade["ticker"],
                            trade_type=last_trade["trade_type"],
                            entry=last_trade["entry_price"],
                            exit_price=last_trade.get("exit_price"),
                            pnl=last_trade.get("pnl"),
                            strategy=last_trade.get("strategy", ""),
                        )
                        if ai_result:
                            st.markdown(f"""<div style='background:rgba(96,165,250,0.06);border:1px solid rgba(96,165,250,0.2);
                                        border-radius:14px;padding:20px;color:#c8d6e5;font-size:13px;line-height:1.7;'>
                              {ai_result}
                            </div>""", unsafe_allow_html=True)

        # ── EXCEL EXPORT ──
        trades_data = db.get_trades()
        if not trades_data.empty:
            xlsx = excel_export.export_portfolio(pd.DataFrame(), trades_data, pd.DataFrame())
            st.download_button("📥 Exportar Trades (Excel)", data=xlsx,
                              file_name="trades_quantum.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with st.expander("🗑️  Eliminar operación por ID"):
            del_id = st.number_input("ID de la operación", min_value=1, step=1, label_visibility="collapsed")
            if st.button("Eliminar"):
                db.delete_trade(int(del_id)); st.success(f"✅ Operación #{del_id} eliminada."); st.rerun()
