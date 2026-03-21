"""
sections/screener.py - Market Screener
Quick scan stocks by fundamental filters using yfinance
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import database as db
from ui_shared import DARK, fmt, kpi

# Popular tickers organized by sector
POPULAR = {
    "Tech (US)":       ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "CRM", "ADBE", "INTC", "AMD", "INTU", "NOW", "ORCL"],
    "Finance (US)":    ["JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP", "BLK", "C"],
    "Healthcare (US)": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "DHR", "BMY"],
    "Energy (US)":     ["XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "VLO", "OXY", "HAL"],
    "Consumer (US)":   ["WMT", "PG", "KO", "PEP", "COST", "HD", "MCD", "NKE", "SBUX", "TGT"],
    "Industrial (US)": ["CAT", "DE", "HON", "GE", "MMM", "UPS", "RTX", "LMT", "BA", "UNP"],
}


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Market Screener</h1>
        <p>Filtrado fundamental · Comparación rápida · Selección Value & Growth</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── INPUT: Tickers ──
    st.markdown("<div class='sec-title'>Selección de Acciones</div>", unsafe_allow_html=True)
    tc1, tc2 = st.columns([2, 1])

    with tc1:
        preset = st.selectbox("Lista predefinida", ["Personalizada"] + list(POPULAR.keys()))
    with tc2:
        if preset == "Personalizada":
            tickers_input = st.text_input("Tickers (separados por coma)",
                                          placeholder="AAPL, MSFT, GOOGL, AMZN")
        else:
            tickers_input = ", ".join(POPULAR[preset])
            st.text_input("Tickers seleccionados", value=tickers_input, disabled=True)

    # ── FILTERS ──
    with st.expander("Filtros fundamentales"):
        fc1, fc2, fc3, fc4 = st.columns(4)
        pe_max = fc1.number_input("P/E máximo", min_value=0.0, value=30.0, step=5.0)
        roe_min = fc2.number_input("ROE mínimo (%)", min_value=0.0, value=10.0, step=5.0)
        margin_min = fc3.number_input("Margen neto mín (%)", min_value=0.0, value=5.0, step=5.0)
        mcap_min = fc4.selectbox("Market Cap mín", ["Sin filtro", ">$1B", ">$10B", ">$100B", ">$1T"])

        fc5, fc6, fc7, fc8 = st.columns(4)
        de_max = fc5.number_input("Deuda/Equity máx", min_value=0.0, value=2.0, step=0.5)
        div_min = fc6.number_input("Div Yield mín (%)", min_value=0.0, value=0.0, step=0.5)
        peg_max = fc7.number_input("PEG máximo", min_value=0.0, value=3.0, step=0.5)
        beta_max = fc8.number_input("Beta máximo", min_value=0.0, value=3.0, step=0.5)

    if st.button("Escanear mercado", type="primary"):
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
        if not tickers:
            st.warning("Ingresa al menos un ticker.")
            return

        with st.spinner(f"Escaneando {len(tickers)} acciones…"):
            results = []
            progress = st.progress(0)

            for i, ticker in enumerate(tickers):
                progress.progress((i + 1) / len(tickers))
                try:
                    tk = yf.Ticker(ticker)
                    info = tk.info
                    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
                        continue

                    price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                    pe = info.get("trailingPE")
                    pe_fwd = info.get("forwardPE")
                    roe = (info.get("returnOnEquity") or 0) * 100
                    margin = (info.get("profitMargins") or 0) * 100
                    mcap = info.get("marketCap", 0)
                    de = (info.get("debtToEquity") or 0) / 100
                    div_y = (info.get("dividendYield") or 0) * 100
                    peg = info.get("pegRatio")
                    beta = info.get("beta")
                    rev_growth = (info.get("revenueGrowth") or 0) * 100
                    earn_growth = (info.get("earningsGrowth") or 0) * 100
                    sector = info.get("sector", "")
                    name = info.get("shortName", ticker)

                    # Apply filters
                    if pe and pe > pe_max:
                        continue
                    if roe < roe_min:
                        continue
                    if margin < margin_min:
                        continue
                    if de > de_max:
                        continue
                    if div_y < div_min:
                        continue
                    if peg and peg > peg_max:
                        continue
                    if beta and beta > beta_max:
                        continue

                    mcap_thresholds = {">$1B": 1e9, ">$10B": 1e10, ">$100B": 1e11, ">$1T": 1e12}
                    if mcap_min != "Sin filtro" and mcap < mcap_thresholds.get(mcap_min, 0):
                        continue

                    # Score (simple scoring: count how many criteria are "good")
                    score = 0
                    if pe and pe < 20: score += 1
                    if roe > 15: score += 1
                    if margin > 15: score += 1
                    if de < 1: score += 1
                    if peg and peg < 1.5: score += 1
                    if rev_growth > 10: score += 1

                    results.append({
                        "Ticker": ticker, "Empresa": name[:25], "Sector": sector,
                        "Precio": price, "P/E": pe, "P/E Fwd": pe_fwd,
                        "ROE %": round(roe, 1), "Margen %": round(margin, 1),
                        "D/E": round(de, 2), "PEG": peg, "Beta": beta,
                        "Div %": round(div_y, 2), "Crec Rev %": round(rev_growth, 1),
                        "Crec Earn %": round(earn_growth, 1),
                        "Mkt Cap": mcap, "Score": score,
                    })
                except Exception:
                    continue

            progress.empty()

        if not results:
            st.warning("Ninguna acción pasó los filtros. Intenta con criterios más amplios.")
            return

        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.session_state["screener_results"] = df

    # ── RESULTS ──
    if "screener_results" in st.session_state:
        df = st.session_state["screener_results"]

        st.markdown("<div class='sec-title'>Resultados del Screener</div>", unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)
        k1.markdown(kpi("Acciones encontradas", str(len(df)), "", "blue"), unsafe_allow_html=True)
        avg_pe = df["P/E"].dropna().mean()
        k2.markdown(kpi("P/E Promedio", f"{avg_pe:.1f}x" if pd.notna(avg_pe) else "—", "", "purple"), unsafe_allow_html=True)
        avg_roe = df["ROE %"].mean()
        k3.markdown(kpi("ROE Promedio", f"{avg_roe:.1f}%", "", "green"), unsafe_allow_html=True)

        # Score color
        def score_color(v):
            if v >= 5:
                return "background-color: rgba(52,211,153,0.15); color: #34d399"
            elif v >= 3:
                return "background-color: rgba(251,191,36,0.15); color: #fbbf24"
            return "background-color: rgba(248,113,113,0.1); color: #f87171"

        display_cols = ["Ticker", "Empresa", "Sector", "Precio", "P/E", "P/E Fwd",
                        "ROE %", "Margen %", "D/E", "PEG", "Div %", "Crec Rev %", "Score"]
        df_show = df[display_cols].copy()

        st.dataframe(
            df_show.style.applymap(score_color, subset=["Score"])
                   .format({"Precio": "${:.2f}", "P/E": "{:.1f}", "P/E Fwd": "{:.1f}",
                            "D/E": "{:.2f}", "PEG": "{:.2f}", "Div %": "{:.2f}%"},
                            na_rep="—"),
            use_container_width=True, hide_index=True
        )

        # ── COMPARISON CHARTS ──
        st.markdown("<div class='sec-title'>Comparación Visual</div>", unsafe_allow_html=True)
        vc1, vc2 = st.columns(2)

        with vc1:
            fig_pe = go.Figure()
            fig_pe.add_trace(go.Bar(
                x=df["Ticker"], y=df["P/E"].fillna(0),
                marker_color=["#34d399" if (v or 99) < 20 else "#fbbf24" if (v or 99) < 30 else "#f87171"
                               for v in df["P/E"]],
                text=[f"{v:.1f}" if pd.notna(v) else "—" for v in df["P/E"]],
                textposition="outside", textfont=dict(color="#94a3b8", size=9),
            ))
            fig_pe.add_hline(y=20, line_dash="dot", line_color="#fbbf24", annotation_text="P/E 20")
            fig_pe.update_layout(**DARK, height=300,
                title=dict(text="P/E Ratio", font=dict(color="#94a3b8", size=13), x=0.5),
                showlegend=False)
            st.plotly_chart(fig_pe, use_container_width=True)

        with vc2:
            fig_roe = go.Figure()
            fig_roe.add_trace(go.Bar(
                x=df["Ticker"], y=df["ROE %"],
                marker_color=["#34d399" if v > 15 else "#fbbf24" if v > 8 else "#f87171"
                               for v in df["ROE %"]],
                text=[f"{v:.1f}%" for v in df["ROE %"]],
                textposition="outside", textfont=dict(color="#94a3b8", size=9),
            ))
            fig_roe.add_hline(y=15, line_dash="dot", line_color="#34d399", annotation_text="ROE 15%")
            fig_roe.update_layout(**DARK, height=300,
                title=dict(text="ROE (%)", font=dict(color="#94a3b8", size=13), x=0.5),
                showlegend=False)
            st.plotly_chart(fig_roe, use_container_width=True)

        # ── ADD TO WATCHLIST ──
        with st.expander("Agregar a Watchlist"):
            add_tickers = st.multiselect("Selecciona tickers", df["Ticker"].tolist())
            if st.button("Agregar seleccionados a Watchlist") and add_tickers:
                for t in add_tickers:
                    row = df[df["Ticker"] == t].iloc[0]
                    db.add_ticker(t, 0, row["Precio"], row.get("Sector", ""), "Desde screener")
                st.success(f"{len(add_tickers)} tickers agregados a la watchlist.")
