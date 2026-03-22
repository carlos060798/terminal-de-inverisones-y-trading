"""
pages/trading_journal.py - Trading Journal section
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import database as db
from ui_shared import DARK, dark_layout, kpi
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

        # D4: Setup + Error Tags
        d4c1, d4c2 = st.columns(2)
        setup_type = d4c1.selectbox("Setup", ["", "Breakout", "Pullback", "Reversal",
                                               "Trend Following", "Range", "Gap", "Earnings Play", "Other"])
        error_type = d4c2.selectbox("Error (si aplica)", ["", "Entrada temprana", "Sin confirmación",
                                                           "Contra tendencia", "Tamaño excesivo",
                                                           "Sin stop loss", "FOMO", "Ninguno"])

        # D5: Trade Rating
        trade_rating = st.slider("Calificación del Trade", 1, 5, 3,
                                 help="1=Terrible, 5=Perfecto")

        # D12: Stop Loss / Take Profit for stocks
        d12c1, d12c2 = st.columns(2)
        sl_stock = d12c1.number_input("Stop Loss ($)", min_value=0.0, step=0.01, format="%.4f", key="tj_sl")
        tp_stock = d12c2.number_input("Take Profit ($)", min_value=0.0, step=0.01, format="%.4f", key="tj_tp")

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
                             lecc, errs,
                             setup_type=setup_type, error_type=error_type,
                             trade_rating=trade_rating,
                             stop_loss=sl_stock if sl_stock > 0 else None,
                             take_profit=tp_stock if tp_stock > 0 else None)
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

        # D2: Expectancy KPI
        try:
            expectancy = (avg_w * wr / 100) - (abs(avg_l) * (100 - wr) / 100)
            exp_color = "green" if expectancy > 0 else "red"
        except Exception:
            expectancy = 0
            exp_color = "red"

        # D5: Average Trade Rating KPI
        try:
            avg_rating = closed["trade_rating"].mean() if "trade_rating" in closed.columns and not closed["trade_rating"].isna().all() else 3.0
        except Exception:
            avg_rating = 3.0

        # D10: Sortino & Calmar ratios
        try:
            daily_returns = closed.sort_values("trade_date")["pnl"].values
            mean_ret = np.mean(daily_returns) if len(daily_returns) > 0 else 0
            downside = daily_returns[daily_returns < 0]
            downside_std = np.std(downside) if len(downside) > 1 else 1
            sortino = mean_ret / downside_std if downside_std != 0 else 0

            eq_curve = np.cumsum(daily_returns)
            running_max = np.maximum.accumulate(eq_curve)
            drawdowns = eq_curve - running_max
            max_dd = abs(np.min(drawdowns)) if len(drawdowns) > 0 else 1
            ann_return = np.sum(daily_returns)
            calmar = ann_return / max_dd if max_dd != 0 else 0
        except Exception:
            sortino, calmar, max_dd = 0, 0, 0

        k5, k6, k7, k8 = st.columns(4)
        k5.markdown(kpi("📈 Expectancy", f"${expectancy:,.2f}", "por trade", exp_color), unsafe_allow_html=True)
        k6.markdown(kpi("⭐ Rating Prom.", f"{avg_rating:.1f}/5", "calificación media", "blue"), unsafe_allow_html=True)
        k7.markdown(kpi("📊 Sortino", f"{sortino:.2f}", "retorno/riesgo bajista", "green" if sortino > 1 else "red"), unsafe_allow_html=True)
        k8.markdown(kpi("📉 Calmar", f"{calmar:.2f}", f"DD Máx: ${max_dd:,.0f}", "green" if calmar > 1 else "red"), unsafe_allow_html=True)

        st.markdown("<div class='sec-title'>Curva de Equity</div>", unsafe_allow_html=True)
        eq = closed.sort_values("trade_date").copy()
        eq["cum"] = eq["pnl"].cumsum()
        eq["color"] = eq["pnl"].apply(lambda x: "#34d399" if x >= 0 else "#f87171")

        # D9: Drawdown overlay calculation
        try:
            eq["running_max"] = eq["cum"].cummax()
            eq["drawdown_pct"] = ((eq["cum"] - eq["running_max"]) / eq["running_max"].replace(0, 1)) * 100
            eq["drawdown_pct"] = eq["drawdown_pct"].fillna(0)
        except Exception:
            eq["drawdown_pct"] = 0

        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(x=eq["trade_date"], y=eq["cum"],
            mode="lines", name="Equity",
            line=dict(color="#60a5fa", width=2.5),
            fill="tozeroy", fillcolor="rgba(96,165,250,0.08)"))
        fig_eq.add_trace(go.Bar(x=eq["trade_date"], y=eq["pnl"],
            marker_color=eq["color"], name="P&L por trade", opacity=0.6,
            yaxis="y2"))
        # D9: Drawdown area trace
        try:
            fig_eq.add_trace(go.Scatter(x=eq["trade_date"], y=eq["drawdown_pct"],
                mode="lines", name="Drawdown %",
                line=dict(color="#f87171", width=1),
                fill="tozeroy", fillcolor="rgba(248,113,113,0.15)",
                yaxis="y3"))
        except Exception:
            pass
        fig_eq.add_hline(y=0, line_dash="dot", line_color="#334155")
        fig_eq.update_layout(**dark_layout(height=350,
            yaxis=dict(title="P&L Acumulado", gridcolor="#1a1a1a", domain=[0.3, 1.0]),
            yaxis2=dict(title="P&L Trade", overlaying="y", side="right", showgrid=False, domain=[0.3, 1.0]),
            yaxis3=dict(title="Drawdown %", anchor="free", overlaying="y", side="right",
                        position=0.95, showgrid=False, domain=[0.0, 0.25],
                        range=[min(eq["drawdown_pct"].min() * 1.2, -1), 0],
                        ticksuffix="%", titlefont=dict(color="#f87171"), tickfont=dict(color="#f87171")),
            legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a", font=dict(size=11))))
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
            import file_saver
            file_saver.save_or_download(xlsx, "trades_quantum.xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              "📥 Exportar Trades (Excel)", key="exp_trades")

        # ── FEATURE 7: Trade Recap Weekly/Monthly ──
        with st.expander("📋 Resumen Periódico"):
            try:
                recap_trades = db.get_trades()
                recap_closed = recap_trades[recap_trades["pnl"].notna()].copy()
                if recap_closed.empty:
                    st.info("No hay trades cerrados para generar resumen.")
                else:
                    recap_closed["trade_date"] = pd.to_datetime(recap_closed["trade_date"])
                    recap_closed["week"] = recap_closed["trade_date"].dt.to_period("W").astype(str)
                    recap_closed["month"] = recap_closed["trade_date"].dt.to_period("M").astype(str)

                    def _calc_recap(group):
                        n = len(group)
                        wins_n = len(group[group["pnl"] > 0])
                        wr_val = (wins_n / n * 100) if n > 0 else 0
                        total_pnl = group["pnl"].sum()
                        best = group["pnl"].max()
                        worst = group["pnl"].min()
                        return pd.Series({
                            "# Trades": n,
                            "Win Rate %": round(wr_val, 1),
                            "Total P&L": round(total_pnl, 2),
                            "Best Trade": round(best, 2),
                            "Worst Trade": round(worst, 2),
                        })

                    recap_tab1, recap_tab2 = st.tabs(["Semanal", "Mensual"])

                    with recap_tab1:
                        weekly = recap_closed.groupby("week").apply(_calc_recap, include_groups=False).reset_index()
                        weekly.rename(columns={"week": "Período"}, inplace=True)
                        weekly = weekly.sort_values("Período", ascending=False)
                        st.dataframe(
                            weekly.style
                                .map(lambda v: "color:#34d399" if isinstance(v, (int, float)) and v > 0
                                     else ("color:#f87171" if isinstance(v, (int, float)) and v < 0 else ""),
                                     subset=["Total P&L", "Best Trade", "Worst Trade"])
                                .format({"Total P&L": "${:+,.2f}", "Best Trade": "${:+,.2f}",
                                          "Worst Trade": "${:+,.2f}", "Win Rate %": "{:.1f}%"}),
                            use_container_width=True, hide_index=True,
                        )

                    with recap_tab2:
                        monthly = recap_closed.groupby("month").apply(_calc_recap, include_groups=False).reset_index()
                        monthly.rename(columns={"month": "Período"}, inplace=True)
                        monthly = monthly.sort_values("Período", ascending=False)
                        st.dataframe(
                            monthly.style
                                .map(lambda v: "color:#34d399" if isinstance(v, (int, float)) and v > 0
                                     else ("color:#f87171" if isinstance(v, (int, float)) and v < 0 else ""),
                                     subset=["Total P&L", "Best Trade", "Worst Trade"])
                                .format({"Total P&L": "${:+,.2f}", "Best Trade": "${:+,.2f}",
                                          "Worst Trade": "${:+,.2f}", "Win Rate %": "{:.1f}%"}),
                            use_container_width=True, hide_index=True,
                        )

                        # Monthly P&L bar chart
                        monthly_chart = monthly.sort_values("Período", ascending=True)
                        fig_monthly = go.Figure(go.Bar(
                            x=monthly_chart["Período"],
                            y=monthly_chart["Total P&L"],
                            marker_color=[
                                "#34d399" if v >= 0 else "#f87171"
                                for v in monthly_chart["Total P&L"]
                            ],
                            text=[f"${v:+,.0f}" for v in monthly_chart["Total P&L"]],
                            textposition="outside",
                            textfont=dict(color="#94a3b8", size=10),
                        ))
                        fig_monthly.add_hline(y=0, line_dash="dot", line_color="#334155")
                        fig_monthly.update_layout(**DARK, height=320,
                            title=dict(text="P&L Mensual", font=dict(color="#94a3b8", size=13), x=0.5),
                            showlegend=False,
                            xaxis_title="Mes", yaxis_title="P&L ($)")
                        st.plotly_chart(fig_monthly, use_container_width=True)

                    # Streaks calculation
                    st.markdown("**Rachas (Consecutive Wins/Losses)**")
                    sorted_trades = recap_closed.sort_values("trade_date")
                    max_win_streak = 0
                    max_loss_streak = 0
                    current_win = 0
                    current_loss = 0
                    for _, row in sorted_trades.iterrows():
                        if row["pnl"] > 0:
                            current_win += 1
                            current_loss = 0
                            max_win_streak = max(max_win_streak, current_win)
                        else:
                            current_loss += 1
                            current_win = 0
                            max_loss_streak = max(max_loss_streak, current_loss)

                    sk1, sk2 = st.columns(2)
                    sk1.markdown(kpi("🔥 Racha Ganadora Máx.", f"{max_win_streak} trades",
                                     "consecutivos", "green"), unsafe_allow_html=True)
                    sk2.markdown(kpi("❄️ Racha Perdedora Máx.", f"{max_loss_streak} trades",
                                     "consecutivos", "red"), unsafe_allow_html=True)
            except Exception as e:
                st.warning(f"Error generando resumen periódico: {e}")

        # ── D3: Win Rate by Strategy ──
        with st.expander("📊 Rendimiento por Estrategia"):
            try:
                strat_trades = db.get_trades()
                strat_closed = strat_trades[strat_trades["exit_price"].notna() & (strat_trades["exit_price"] > 0)].copy()
                if strat_closed.empty:
                    st.info("No hay trades cerrados para analizar por estrategia.")
                else:
                    # Use setup_type column; group empty as "Sin clasificar"
                    if "setup_type" in strat_closed.columns:
                        strat_closed["_strategy"] = strat_closed["setup_type"].fillna("").astype(str).str.strip()
                    else:
                        strat_closed["_strategy"] = ""
                    strat_closed.loc[strat_closed["_strategy"] == "", "_strategy"] = "Sin clasificar"

                    strat_rows = []
                    for sname, grp in strat_closed.groupby("_strategy"):
                        n = len(grp)
                        w = len(grp[grp["pnl"] > 0])
                        l = len(grp[grp["pnl"] <= 0])
                        wr_s = (w / n * 100) if n > 0 else 0
                        avg_pnl = grp["pnl"].mean()
                        total_pnl_s = grp["pnl"].sum()
                        gross_profit = grp[grp["pnl"] > 0]["pnl"].sum()
                        gross_loss = abs(grp[grp["pnl"] <= 0]["pnl"].sum())
                        pf_s = gross_profit / gross_loss if gross_loss > 0 else 0
                        strat_rows.append({
                            "Estrategia": sname,
                            "# Trades": n,
                            "Win Rate %": round(wr_s, 1),
                            "Avg P&L": round(avg_pnl, 2),
                            "Total P&L": round(total_pnl_s, 2),
                            "Profit Factor": round(pf_s, 2),
                        })

                    strat_df = pd.DataFrame(strat_rows).sort_values("Total P&L", ascending=False)

                    def _strat_color(v):
                        if isinstance(v, (int, float)) and not pd.isna(v):
                            if v > 0:
                                return "color:#34d399"
                            elif v < 0:
                                return "color:#f87171"
                        return "color:#475569"

                    st.dataframe(
                        strat_df.style
                            .map(_strat_color, subset=["Avg P&L", "Total P&L"])
                            .format({
                                "Win Rate %": "{:.1f}%",
                                "Avg P&L": "${:+,.2f}",
                                "Total P&L": "${:+,.2f}",
                                "Profit Factor": "{:.2f}x",
                            }),
                        use_container_width=True, hide_index=True,
                    )
            except Exception as e:
                st.warning(f"Error generando rendimiento por estrategia: {e}")

        # ── D7: P&L by Day of Week ──
        with st.expander("📅 P&L por Dia de Semana"):
            try:
                dow_trades = db.get_trades()
                dow_closed = dow_trades[dow_trades["pnl"].notna()].copy()
                if dow_closed.empty:
                    st.info("No hay trades cerrados para analizar por dia.")
                else:
                    dow_closed["trade_date"] = pd.to_datetime(dow_closed["trade_date"])
                    dow_closed["day_num"] = dow_closed["trade_date"].dt.dayofweek
                    day_names = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes"}
                    dow_closed["day_name"] = dow_closed["day_num"].map(day_names)

                    dow_pnl = dow_closed.groupby(["day_num", "day_name"])["pnl"].sum().reset_index()
                    dow_pnl = dow_pnl.sort_values("day_num")

                    colors_dow = ["#34d399" if v >= 0 else "#f87171" for v in dow_pnl["pnl"]]

                    fig_dow = go.Figure(go.Bar(
                        x=dow_pnl["day_name"],
                        y=dow_pnl["pnl"],
                        marker_color=colors_dow,
                        text=[f"${v:+,.0f}" for v in dow_pnl["pnl"]],
                        textposition="outside",
                        textfont=dict(color="#94a3b8", size=11),
                    ))
                    fig_dow.add_hline(y=0, line_dash="dot", line_color="#334155")
                    fig_dow.update_layout(**dark_layout(
                        height=350,
                        title=dict(text="P&L por Dia de Semana", font=dict(color="#94a3b8", size=13), x=0.5),
                        showlegend=False,
                        xaxis=dict(title="Dia", categoryorder="array",
                                   categoryarray=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]),
                        yaxis=dict(title="P&L ($)", gridcolor="#1a1a1a"),
                    ))
                    st.plotly_chart(fig_dow, use_container_width=True)

                    best_day = dow_pnl.loc[dow_pnl["pnl"].idxmax()]
                    worst_day = dow_pnl.loc[dow_pnl["pnl"].idxmin()]
                    bd1, bd2 = st.columns(2)
                    bd1.markdown(kpi("Mejor Dia", best_day["day_name"],
                                     f"${best_day['pnl']:+,.2f}", "green"), unsafe_allow_html=True)
                    bd2.markdown(kpi("Peor Dia", worst_day["day_name"],
                                     f"${worst_day['pnl']:+,.2f}", "red"), unsafe_allow_html=True)
            except Exception as e:
                st.warning(f"Error generando P&L por dia: {e}")

        with st.expander("🗑️  Eliminar operación por ID"):
            del_id = st.number_input("ID de la operación", min_value=1, step=1, label_visibility="collapsed")
            if st.button("Eliminar"):
                db.delete_trade(int(del_id)); st.success(f"✅ Operación #{del_id} eliminada."); st.rerun()
