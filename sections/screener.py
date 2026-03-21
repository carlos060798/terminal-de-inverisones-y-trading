"""
sections/screener.py - Market Screener
Quick scan stocks by fundamental filters using yfinance & Finviz
"""
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
import database as db
from ui_shared import DARK, fmt, kpi

try:
    from finvizfinance.screener.overview import Overview
    HAS_FINVIZ = True
except ImportError:
    HAS_FINVIZ = False

# Popular tickers organized by sector
POPULAR = {
    "Tech (US)":       ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "CRM", "ADBE", "INTC", "AMD", "INTU", "NOW", "ORCL"],
    "Finance (US)":    ["JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP", "BLK", "C"],
    "Healthcare (US)": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "DHR", "BMY"],
    "Energy (US)":     ["XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "VLO", "OXY", "HAL"],
    "Consumer (US)":   ["WMT", "PG", "KO", "PEP", "COST", "HD", "MCD", "NKE", "SBUX", "TGT"],
    "Industrial (US)": ["CAT", "DE", "HON", "GE", "MMM", "UPS", "RTX", "LMT", "BA", "UNP"],
}


def _render_yfinance_screener():
    """Original yfinance-based screener content."""
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

        # ── QUANT SCORE (Multi-Factor: Value + Quality + Growth + Momentum + Safety) ──
        try:
            if len(df) >= 2:
                # Value: lower P/E is better (rank ascending, best = highest rank)
                pe_vals = df["P/E"].fillna(df["P/E"].max() if df["P/E"].notna().any() else 999)
                df["_pe_rank"] = pe_vals.rank(ascending=True, pct=True) * 20

                # Quality: higher ROE is better
                df["_roe_rank"] = df["ROE %"].rank(ascending=True, pct=True) * 20

                # Growth: higher revenue growth is better
                df["_rev_rank"] = df["Crec Rev %"].rank(ascending=True, pct=True) * 20

                # Momentum: higher earnings growth is better
                df["_earn_rank"] = df["Crec Earn %"].rank(ascending=True, pct=True) * 20

                # Safety: lower D/E is better
                de_vals = df["D/E"].fillna(df["D/E"].max() if df["D/E"].notna().any() else 5)
                df["_de_rank"] = de_vals.rank(ascending=False, pct=True) * 20

                df["Quant"] = (
                    df["_pe_rank"].fillna(0) +
                    df["_roe_rank"].fillna(0) +
                    df["_rev_rank"].fillna(0) +
                    df["_earn_rank"].fillna(0) +
                    df["_de_rank"].fillna(0)
                ).round(0).astype(int)

                # Drop temp columns
                df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
            else:
                df["Quant"] = 50  # Single stock gets neutral score
        except Exception:
            df["Quant"] = None

        df = df.sort_values("Quant", ascending=False, na_position="last")
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

        # Quant score color
        def quant_color(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "color:#475569"
            if v >= 75:
                return "background-color: rgba(52,211,153,0.2); color: #34d399; font-weight: 700"
            elif v >= 50:
                return "background-color: rgba(96,165,250,0.15); color: #60a5fa"
            elif v >= 30:
                return "background-color: rgba(251,191,36,0.15); color: #fbbf24"
            return "background-color: rgba(248,113,113,0.15); color: #f87171"

        display_cols = ["Ticker", "Empresa", "Sector", "Precio", "P/E", "P/E Fwd",
                        "ROE %", "Margen %", "D/E", "PEG", "Div %", "Crec Rev %", "Score", "Quant"]
        available_cols = [c for c in display_cols if c in df.columns]
        df_show = df[available_cols].copy()

        style_obj = df_show.style.map(score_color, subset=["Score"])
        if "Quant" in df_show.columns:
            style_obj = style_obj.map(quant_color, subset=["Quant"])

        st.dataframe(
            style_obj.format({"Precio": "${:.2f}", "P/E": "{:.1f}", "P/E Fwd": "{:.1f}",
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


def _render_finviz_screener():
    """Finviz-based screener for faster bulk screening."""
    if not HAS_FINVIZ:
        st.warning(
            "El paquete `finvizfinance` no está instalado. "
            "Instálalo con: `pip install finvizfinance`"
        )
        return

    st.markdown("<div class='sec-title'>Filtros Finviz</div>", unsafe_allow_html=True)

    fc1, fc2 = st.columns(2)
    with fc1:
        sector = st.selectbox(
            "Sector",
            ["Any", "Technology", "Financial", "Healthcare", "Energy",
             "Consumer Cyclical", "Consumer Defensive", "Industrials",
             "Basic Materials", "Communication Services", "Real Estate", "Utilities"],
            key="fvz_sector",
        )
        pe_filter = st.selectbox(
            "P/E Ratio",
            ["Any", "Under 5", "Under 10", "Under 15", "Under 20",
             "Under 25", "Under 30", "Under 40", "Under 50",
             "Over 5", "Over 10", "Over 15", "Over 20", "Over 50"],
            key="fvz_pe",
        )
    with fc2:
        mcap_filter = st.selectbox(
            "Market Cap",
            ["Any", "+Mega (over $200bln)", "+Large (over $10bln)",
             "+Mid (over $2bln)", "+Small (over $300mln)",
             "-Mega (under $200bln)", "-Large (under $10bln)",
             "-Mid (under $2bln)", "-Small (under $300mln)", "-Micro (under $50mln)"],
            key="fvz_mcap",
        )
        eps_growth = st.selectbox(
            "EPS Growth Past 5 Years",
            ["Any", "Over 5%", "Over 10%", "Over 15%", "Over 20%",
             "Over 25%", "Over 30%"],
            key="fvz_eps",
        )

    if st.button("Buscar en Finviz", type="primary", key="fvz_btn"):
        try:
            with st.spinner("Consultando Finviz..."):
                filters: dict = {}
                if sector != "Any":
                    filters["Sector"] = sector
                if mcap_filter != "Any":
                    filters["Market Cap."] = mcap_filter
                if pe_filter != "Any":
                    filters["P/E"] = pe_filter
                if eps_growth != "Any":
                    filters["EPS growthpast 5 years"] = eps_growth

                foverview = Overview()
                foverview.set_filter(filters_dict=filters)
                df = foverview.screener_view()

            if df is None or df.empty:
                st.warning("Finviz no devolvió resultados para estos filtros.")
                return

            st.session_state["finviz_results"] = df
        except Exception as e:
            st.error(f"Error al consultar Finviz: {e}")
            return

    # ── RESULTS ──
    if "finviz_results" in st.session_state:
        df = st.session_state["finviz_results"]

        st.markdown("<div class='sec-title'>Resultados Finviz</div>", unsafe_allow_html=True)

        k1, k2, k3 = st.columns(3)
        k1.markdown(kpi("Acciones encontradas", str(len(df)), "", "blue"), unsafe_allow_html=True)

        if "P/E" in df.columns:
            pe_col = pd.to_numeric(df["P/E"], errors="coerce")
            avg_pe = pe_col.dropna().mean()
            k2.markdown(
                kpi("P/E Promedio", f"{avg_pe:.1f}x" if pd.notna(avg_pe) else "—", "", "purple"),
                unsafe_allow_html=True,
            )
        else:
            k2.markdown(kpi("P/E Promedio", "—", "", "purple"), unsafe_allow_html=True)

        if "Price" in df.columns:
            price_col = pd.to_numeric(df["Price"], errors="coerce")
            avg_price = price_col.dropna().mean()
            k3.markdown(
                kpi("Precio Promedio", f"${avg_price:.2f}" if pd.notna(avg_price) else "—", "", "green"),
                unsafe_allow_html=True,
            )
        else:
            k3.markdown(kpi("Precio Promedio", "—", "", "green"), unsafe_allow_html=True)

        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── HEATMAP: P/E by Sector ──
        if "P/E" in df.columns and "Sector" in df.columns:
            st.markdown("<div class='sec-title'>Heatmap: P/E por Sector</div>", unsafe_allow_html=True)
            try:
                heat_df = df[["Ticker", "Sector", "P/E"]].copy()
                heat_df["P/E"] = pd.to_numeric(heat_df["P/E"], errors="coerce")
                heat_df = heat_df.dropna(subset=["P/E"])

                if not heat_df.empty:
                    pivot = heat_df.groupby("Sector")["P/E"].mean().reset_index()
                    pivot.columns = ["Sector", "Avg P/E"]
                    pivot = pivot.sort_values("Avg P/E", ascending=True)

                    fig_heat = px.bar(
                        pivot,
                        x="Avg P/E",
                        y="Sector",
                        orientation="h",
                        color="Avg P/E",
                        color_continuous_scale=["#34d399", "#fbbf24", "#f87171"],
                        text=pivot["Avg P/E"].apply(lambda v: f"{v:.1f}"),
                    )
                    fig_heat.update_layout(
                        **DARK,
                        height=max(300, len(pivot) * 45),
                        title=dict(
                            text="P/E Promedio por Sector",
                            font=dict(color="#94a3b8", size=13),
                            x=0.5,
                        ),
                        coloraxis_showscale=False,
                        showlegend=False,
                    )
                    fig_heat.update_traces(textposition="outside", textfont=dict(color="#94a3b8", size=10))
                    st.plotly_chart(fig_heat, use_container_width=True)
                else:
                    st.info("No hay datos numéricos de P/E para generar el heatmap.")
            except Exception as e:
                st.warning(f"No se pudo generar el heatmap: {e}")


HEATMAP_TICKERS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMZN"],
    "Healthcare": ["JNJ", "UNH", "PFE", "LLY", "ABBV", "MRK"],
    "Finance": ["JPM", "BAC", "GS", "V", "MA", "BRK-B"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC"],
    "Consumer": ["WMT", "PG", "KO", "PEP", "COST", "MCD"],
    "Industrial": ["CAT", "HON", "UNP", "RTX", "DE", "GE"],
}


def _render_sector_heatmap():
    """FinViz-style sector heatmap using treemap colored by daily change %."""
    try:
        st.markdown("<div class='sec-title'>Sector Heatmap — Cambio Diario %</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                    border-radius:12px;padding:14px;margin-bottom:16px;color:#94a3b8;font-size:12px;'>
          Mapa de calor estilo FinViz. El tamaño representa la capitalización de mercado relativa.
          El color indica el cambio porcentual del día: <span style='color:#34d399'>verde = positivo</span>,
          <span style='color:#f87171'>rojo = negativo</span>.
        </div>""", unsafe_allow_html=True)

        if st.button("Cargar Sector Heatmap", type="primary", key="heatmap_btn"):
            # Flatten tickers
            all_tickers = []
            ticker_sector = {}
            for sector, ticks in HEATMAP_TICKERS.items():
                for t in ticks:
                    all_tickers.append(t)
                    ticker_sector[t] = sector

            with st.spinner(f"Descargando datos de {len(all_tickers)} acciones…"):
                hm_rows = []
                for tk in all_tickers:
                    try:
                        obj = yf.Ticker(tk)
                        fi = obj.fast_info
                        hist = obj.history(period="2d")
                        price = fi.last_price or 0
                        prev = hist["Close"].iloc[-2] if len(hist) >= 2 else price
                        chg = ((price - prev) / prev * 100) if prev else 0
                        mcap = fi.market_cap or 1e9
                        hm_rows.append({
                            "Ticker": tk,
                            "Sector": ticker_sector[tk],
                            "Cambio %": round(chg, 2),
                            "Mkt Cap": mcap,
                            "Precio": round(price, 2),
                        })
                    except Exception:
                        hm_rows.append({
                            "Ticker": tk,
                            "Sector": ticker_sector[tk],
                            "Cambio %": 0,
                            "Mkt Cap": 1e9,
                            "Precio": 0,
                        })

            hm_df = pd.DataFrame(hm_rows)
            hm_df["abs_mcap"] = hm_df["Mkt Cap"].abs()
            hm_df["Label"] = hm_df.apply(
                lambda r: f"{r['Ticker']}<br>{r['Cambio %']:+.2f}%", axis=1
            )

            # Treemap
            fig_tm = px.treemap(
                hm_df,
                path=["Sector", "Ticker"],
                values="abs_mcap",
                color="Cambio %",
                color_continuous_scale=["#dc2626", "#7f1d1d", "#1a1a1a", "#064e3b", "#059669"],
                color_continuous_midpoint=0,
                custom_data=["Cambio %", "Precio"],
            )
            fig_tm.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%",
                textfont=dict(size=12),
            )
            fig_tm.update_layout(
                paper_bgcolor="#000000",
                plot_bgcolor="#0a0a0a",
                font=dict(color="#94a3b8", size=12),
                margin=dict(l=4, r=4, t=36, b=4),
                height=550,
                title=dict(text="Sector Heatmap — Cambio Diario", font=dict(color="#94a3b8", size=14), x=0.5),
                coloraxis_colorbar=dict(
                    title="Cambio %",
                    ticksuffix="%",
                    bgcolor="#0a0a0a",
                    bordercolor="#1a1a1a",
                ),
            )
            st.plotly_chart(fig_tm, use_container_width=True)

            # Summary table
            st.markdown("<div class='sec-title'>Resumen por Sector</div>", unsafe_allow_html=True)
            sector_summary = hm_df.groupby("Sector").agg(
                Tickers=("Ticker", "count"),
                **{"Cambio Prom %": ("Cambio %", "mean")},
                **{"Mejor": ("Cambio %", "max")},
                **{"Peor": ("Cambio %", "min")},
            ).round(2).reset_index()
            sector_summary = sector_summary.sort_values("Cambio Prom %", ascending=False)

            def sect_clr(v):
                if isinstance(v, (int, float)) and not pd.isna(v):
                    return "color:#34d399" if v >= 0 else "color:#f87171"
                return "color:#475569"

            st.dataframe(
                sector_summary.style.map(sect_clr, subset=["Cambio Prom %", "Mejor", "Peor"])
                    .format({"Cambio Prom %": "{:+.2f}%", "Mejor": "{:+.2f}%", "Peor": "{:+.2f}%"}),
                use_container_width=True, hide_index=True,
            )

    except Exception as e:
        st.error(f"Error al generar el heatmap: {e}")


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Market Screener</h1>
        <p>Filtrado fundamental · Comparación rápida · Selección Value & Growth</p>
      </div>
    </div>""", unsafe_allow_html=True)

    tab_yf, tab_fvz, tab_heatmap = st.tabs(["📊 yfinance Screener", "🔍 Finviz Screener", "🗺️ Sector Heatmap"])

    with tab_yf:
        _render_yfinance_screener()

    with tab_fvz:
        _render_finviz_screener()

    with tab_heatmap:
        _render_sector_heatmap()
