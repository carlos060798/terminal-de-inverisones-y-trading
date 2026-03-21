"""
pages/watchlist.py - Watchlist & Portfolio section
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import database as db
from ui_shared import DARK, fmt, kpi


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Watchlist & Cartera</h1>
        <p>Precios en tiempo real · Portfolio tracker · Distribución por sector</p>
      </div>
    </div>""", unsafe_allow_html=True)

    with st.expander("➕  Agregar nueva posición"):
        c1,c2,c3,c4 = st.columns(4)
        new_tick  = c1.text_input("Ticker", placeholder="AAPL")
        new_share = c2.number_input("Acciones", min_value=0.0, step=1.0)
        new_cost  = c3.number_input("Precio promedio ($)", min_value=0.0, step=0.01)
        new_sect  = c4.selectbox("Sector", ["","Tecnología","Salud","Finanzas","Energía",
                                             "Consumo","Industria","Materiales","Utilities","Otro"])
        c5, c6 = st.columns([3,1])
        new_notes = c5.text_input("Notas")
        with c6:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Agregar ticker"):
                if new_tick.strip():
                    db.add_ticker(new_tick.strip(), new_share, new_cost, new_sect, new_notes)
                    st.success(f"✅ {new_tick.upper()} agregado.")
                    st.rerun()

    wl = db.get_watchlist()
    if wl.empty:
        st.info("Tu watchlist está vacía. Agrega tickers para comenzar.")
    else:
        tickers = wl["ticker"].tolist()
        with st.spinner("📡 Actualizando precios de mercado…"):
            rows = []
            for tk in tickers:
                try:
                    obj  = yf.Ticker(tk)
                    fi   = obj.fast_info
                    hist = obj.history(period="2d")
                    price = fi.last_price or 0
                    prev  = hist["Close"].iloc[-2] if len(hist) >= 2 else price
                    chg   = ((price - prev) / prev * 100) if prev else 0
                    info  = obj.info
                    rows.append({"ticker": tk, "Precio": price, "Cambio %": chg,
                                 "P/E": info.get("trailingPE"), "52W High": info.get("fiftyTwoWeekHigh"),
                                 "52W Low": info.get("fiftyTwoWeekLow"), "Mkt Cap": fi.market_cap})
                except:
                    rows.append({"ticker": tk, "Precio": None, "Cambio %": None,
                                 "P/E": None, "52W High": None, "52W Low": None, "Mkt Cap": None})

        mkt = pd.DataFrame(rows)
        df  = wl.merge(mkt, on="ticker", how="left")
        df["Valor"]  = df["shares"] * df["Precio"]
        df["P&L $"]  = (df["Precio"] - df["avg_cost"]) * df["shares"]
        df["P&L %"]  = ((df["Precio"] - df["avg_cost"]) / df["avg_cost"] * 100).where(df["avg_cost"] > 0)

        total_inv = (df["avg_cost"] * df["shares"]).sum()
        total_val = df["Valor"].sum()
        total_pnl = total_val - total_inv
        total_pct = (total_pnl / total_inv * 100) if total_inv > 0 else 0

        # ── Portfolio KPIs ──
        k1,k2,k3,k4 = st.columns(4)
        k1.markdown(kpi("💼 Valor Total", fmt(total_val), f"{len(df)} posiciones", "blue"), unsafe_allow_html=True)
        k2.markdown(kpi("💵 Capital Invertido", fmt(total_inv), "", "purple"), unsafe_allow_html=True)
        pnl_color = "green" if total_pnl >= 0 else "red"
        pnl_sign  = "+" if total_pnl >= 0 else ""
        k3.markdown(kpi("📈 P&L Total", fmt(total_pnl), f"{pnl_sign}{total_pct:.2f}%", pnl_color), unsafe_allow_html=True)
        best_pos = df.loc[df["P&L %"].idxmax(), "ticker"] if not df["P&L %"].isna().all() else "—"
        k4.markdown(kpi("🏆 Mejor Posición", best_pos, "", "green"), unsafe_allow_html=True)

        st.markdown("<div class='sec-title'>Tabla de Posiciones</div>", unsafe_allow_html=True)
        tbl = df[["ticker","sector","shares","avg_cost","Precio","Cambio %","P/E","Valor","P&L $","P&L %"]].copy()
        tbl.columns = ["Ticker","Sector","Acciones","Costo Prom.","Precio","Cambio %","P/E","Valor ($)","P&L ($)","P&L %"]

        def clr(v):
            if v is None or (isinstance(v,float) and pd.isna(v)): return "color:#475569"
            return "color:#34d399" if v >= 0 else "color:#f87171"

        st.dataframe(
            tbl.style.applymap(clr, subset=["Cambio %","P&L ($)","P&L %"])
                     .format({"Costo Prom.":"${:.2f}","Precio":"${:.2f}","Cambio %":"{:+.2f}%",
                              "Valor ($)":"${:,.0f}","P&L ($)":"${:+,.0f}","P&L %":"{:+.2f}%","Acciones":"{:.2f}"},
                              na_rep="—"),
            use_container_width=True, hide_index=True
        )

        # ── Charts ──
        st.markdown("<div class='sec-title'>Distribución & Performance</div>", unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            pie_d = df[df["Valor"] > 0]
            if not pie_d.empty:
                fig_p = px.pie(pie_d, names="ticker", values="Valor", hole=0.5,
                               color_discrete_sequence=["#60a5fa","#34d399","#a78bfa","#fbbf24",
                                                        "#f87171","#38bdf8","#4ade80","#e879f9"])
                fig_p.update_traces(textposition="inside", textinfo="percent+label",
                                    textfont=dict(color="white", size=11))
                fig_p.update_layout(**DARK, height=320,
                    title=dict(text="Composición de Cartera", font=dict(color="#94a3b8",size=13), x=0.5),
                    showlegend=False)
                st.plotly_chart(fig_p, use_container_width=True)

        with cc2:
            pnl_d = df[df["shares"] > 0].dropna(subset=["P&L $"])
            if not pnl_d.empty:
                colors_pnl = ["#34d399" if v >= 0 else "#f87171" for v in pnl_d["P&L $"]]
                fig_pnl = go.Figure(go.Bar(
                    x=pnl_d["ticker"], y=pnl_d["P&L $"],
                    marker_color=colors_pnl,
                    text=[f"${v:+,.0f}" for v in pnl_d["P&L $"]],
                    textposition="outside", textfont=dict(color="#94a3b8", size=11),
                ))
                fig_pnl.update_layout(**DARK, height=320,
                    title=dict(text="P&L por Posición", font=dict(color="#94a3b8",size=13), x=0.5),
                    showlegend=False)
                st.plotly_chart(fig_pnl, use_container_width=True)

        # ── Price chart ──
        st.markdown("<div class='sec-title'>Gráfico de Precio</div>", unsafe_allow_html=True)
        tc1, tc2 = st.columns([2,1])
        sel = tc1.selectbox("Selecciona ticker", tickers, label_visibility="collapsed")
        per = tc2.select_slider("Período", ["1mo","3mo","6mo","1y","2y","5y"], value="6mo", label_visibility="collapsed")
        if sel:
            hd = yf.Ticker(sel).history(period=per)
            if not hd.empty:
                hd["MA20"] = hd["Close"].rolling(20).mean()
                hd["MA50"] = hd["Close"].rolling(50).mean()
                fig_c = go.Figure()
                fig_c.add_trace(go.Candlestick(x=hd.index, open=hd["Open"], high=hd["High"],
                    low=hd["Low"], close=hd["Close"], name=sel,
                    increasing=dict(line=dict(color="#34d399"), fillcolor="#34d399"),
                    decreasing=dict(line=dict(color="#f87171"), fillcolor="#f87171")))
                fig_c.add_trace(go.Scatter(x=hd.index, y=hd["MA20"], name="MA20",
                    line=dict(color="#fbbf24", width=1.2)))
                fig_c.add_trace(go.Scatter(x=hd.index, y=hd["MA50"], name="MA50",
                    line=dict(color="#a78bfa", width=1.2)))
                fig_c.update_layout(**DARK, height=380,
                    xaxis_rangeslider_visible=False,
                    legend=dict(bgcolor="#0f1923", bordercolor="#1e2d40", font=dict(size=11)),
                    title=dict(text=f"{sel} — {per}", font=dict(color="#94a3b8",size=13)))
                st.plotly_chart(fig_c, use_container_width=True)

        # ── Remove ──
        with st.expander("🗑️  Eliminar ticker"):
            del_t = st.selectbox("Ticker a eliminar", [""] + tickers, label_visibility="collapsed")
            if del_t and st.button(f"Eliminar {del_t}"):
                db.remove_ticker(del_t); st.success(f"✅ {del_t} eliminado."); st.rerun()
