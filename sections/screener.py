"""
sections/screener.py - Market Screener
Quick scan stocks by fundamental filters using yfinance & Finviz
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import time
import textwrap
import plotly.graph_objects as go
import plotly.express as px
import database as db
from ui_shared import DARK, dark_layout, fmt, kpi

try:
    from finvizfinance.screener.overview import Overview
    HAS_FINVIZ = True
except ImportError:
    HAS_FINVIZ = False

from utils import visual_components as vc
import streamlit as st

AVAILABLE_METRICS = {
    "P/E Ratio": {"key": "trailingPE", "type": "range", "min": 0, "max": 200, "default": (0, 50), "step": 1.0, "format": "%.1f"},
    "Forward P/E": {"key": "forwardPE", "type": "range", "min": 0, "max": 200, "default": (0, 40), "step": 1.0, "format": "%.1f"},
    "P/B Ratio": {"key": "priceToBook", "type": "range", "min": 0, "max": 50, "default": (0, 10), "step": 0.5, "format": "%.1f"},
    "P/S Ratio": {"key": "priceToSalesTrailing12Months", "type": "range", "min": 0, "max": 50, "default": (0, 10), "step": 0.5, "format": "%.1f"},
    "EV/EBITDA": {"key": "enterpriseToEbitda", "type": "range", "min": 0, "max": 100, "default": (0, 20), "step": 1.0, "format": "%.1f"},
    "Market Cap ($B)": {"key": "marketCap", "type": "range", "min": 0, "max": 5000, "default": (1, 5000), "step": 1.0, "format": "%.0f", "scale": 1e9},
    "Dividend Yield (%)": {"key": "dividendYield", "type": "range", "min": 0.0, "max": 20.0, "default": (0.0, 20.0), "step": 0.1, "format": "%.1f", "scale": 100},
    "Revenue Growth (%)": {"key": "revenueGrowth", "type": "range", "min": -50, "max": 200, "default": (0, 200), "step": 1.0, "format": "%.0f", "scale": 100},
    "Earnings Growth (%)": {"key": "earningsGrowth", "type": "range", "min": -100, "max": 500, "default": (-100, 500), "step": 1.0, "format": "%.0f", "scale": 100},
    "Profit Margin (%)": {"key": "profitMargins", "type": "range", "min": -50, "max": 100, "default": (0, 100), "step": 1.0, "format": "%.0f", "scale": 100},
    "Operating Margin (%)": {"key": "operatingMargins", "type": "range", "min": -50, "max": 100, "default": (0, 100), "step": 1.0, "format": "%.0f", "scale": 100},
    "ROE (%)": {"key": "returnOnEquity", "type": "range", "min": -50, "max": 200, "default": (0, 200), "step": 1.0, "format": "%.0f", "scale": 100},
    "ROA (%)": {"key": "returnOnAssets", "type": "range", "min": -30, "max": 100, "default": (0, 100), "step": 1.0, "format": "%.0f", "scale": 100},
    "Debt/Equity": {"key": "debtToEquity", "type": "range", "min": 0, "max": 500, "default": (0, 200), "step": 5.0, "format": "%.0f"},
    "Current Ratio": {"key": "currentRatio", "type": "range", "min": 0, "max": 10, "default": (1, 10), "step": 0.1, "format": "%.1f"},
    "Quick Ratio": {"key": "quickRatio", "type": "range", "min": 0, "max": 10, "default": (0.5, 10), "step": 0.1, "format": "%.1f"},
    "Beta": {"key": "beta", "type": "range", "min": -2, "max": 5, "default": (0, 3), "step": 0.1, "format": "%.1f"},
    "52W High (%)": {"key": "fiftyTwoWeekHigh_pct", "type": "range", "min": -80, "max": 20, "default": (-30, 0), "step": 1.0, "format": "%.0f", "computed": True},
    "Avg Volume (M)": {"key": "averageVolume", "type": "range", "min": 0, "max": 100, "default": (0.5, 100), "step": 0.5, "format": "%.1f", "scale": 1e6},
    "PEG Ratio": {"key": "pegRatio", "type": "range", "min": 0, "max": 10, "default": (0, 3), "step": 0.1, "format": "%.1f"},
    "Price/FCF": {"key": "priceToFreeCashflows", "type": "range", "min": 0, "max": 100, "default": (0, 30), "step": 1.0, "format": "%.0f"},
    "Insider Ownership (%)": {"key": "heldPercentInsiders", "type": "range", "min": 0, "max": 100, "default": (0, 100), "step": 1.0, "format": "%.0f", "scale": 100},
    "Institutional Ownership (%)": {"key": "heldPercentInstitutions", "type": "range", "min": 0, "max": 100, "default": (0, 100), "step": 1.0, "format": "%.0f", "scale": 100},
    "Short Ratio": {"key": "shortRatio", "type": "range", "min": 0, "max": 30, "default": (0, 10), "step": 0.5, "format": "%.1f"},
    "Payout Ratio (%)": {"key": "payoutRatio", "type": "range", "min": 0, "max": 200, "default": (0, 100), "step": 5.0, "format": "%.0f", "scale": 100},
}

FILTER_PRESETS = {
    "Personalizado": [],
    "Value Investing": ["P/E Ratio", "P/B Ratio", "Dividend Yield (%)", "Debt/Equity", "ROE (%)"],
    "Growth": ["Revenue Growth (%)", "Earnings Growth (%)", "Profit Margin (%)", "Forward P/E"],
    "Quality Institucional": ["ROE (%)", "Profit Margin (%)", "Current Ratio", "Debt/Equity", "Revenue Growth (%)"],
    "Dividend": ["Dividend Yield (%)", "Payout Ratio (%)", "Debt/Equity", "Current Ratio"],
    "Safe Haven": ["Beta", "Current Ratio", "Debt/Equity", "Dividend Yield (%)"],
}

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
    """Original yfinance-based screener content with dynamic configurable filters."""
    # ── INPUT: Tickers ──
    st.markdown("<div class='sec-title'>Seleccion de Acciones</div>", unsafe_allow_html=True)
    tc1, tc2 = st.columns([2, 1])

    with tc1:
        ticker_preset = st.selectbox("Lista predefinida", ["Personalizada"] + list(POPULAR.keys()), key="yf_ticker_preset")
    with tc2:
        if ticker_preset == "Personalizada":
            tickers_input = st.text_input("Tickers (separados por coma)",
                                          placeholder="AAPL, MSFT, GOOGL, AMZN")
        else:
            tickers_input = ", ".join(POPULAR[ticker_preset])
            st.text_input("Tickers seleccionados", value=tickers_input, disabled=True)

    # ── DYNAMIC CONFIGURABLE FILTERS ──
    with st.expander("Filtros fundamentales", expanded=True):

        # Initialize active filters in session state
        if 'screener_active_filters' not in st.session_state:
            st.session_state.screener_active_filters = ["P/E Ratio", "Market Cap ($B)", "Dividend Yield (%)", "ROE (%)", "Debt/Equity"]

        # Preset selector + Add filter
        preset_col, add_col = st.columns([3, 2])
        with preset_col:
            preset = st.selectbox("Preset de filtros", list(FILTER_PRESETS.keys()), key="filter_preset_select")
            if preset != "Personalizado":
                st.session_state.screener_active_filters = list(FILTER_PRESETS[preset])

        with add_col:
            available = [m for m in AVAILABLE_METRICS if m not in st.session_state.screener_active_filters]
            new_filter = st.selectbox("Agregar filtro", ["(seleccionar)"] + available, key="add_filter_select")
            if new_filter != "(seleccionar)":
                st.session_state.screener_active_filters.append(new_filter)
                st.rerun()

        # Render active filters dynamically
        filter_values = {}
        cols_per_row = 4
        active = st.session_state.screener_active_filters
        for i in range(0, len(active), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(active):
                    break
                metric_name = active[idx]
                metric = AVAILABLE_METRICS[metric_name]
                with col:
                    sub_cols = st.columns([4, 1])
                    with sub_cols[0]:
                        val = st.slider(
                            metric_name,
                            min_value=float(metric["min"]),
                            max_value=float(metric["max"]),
                            value=(float(metric["default"][0]), float(metric["default"][1])),
                            step=float(metric.get("step", 1.0)),
                            format=metric.get("format", "%.1f"),
                            key=f"filter_{metric_name}"
                        )
                        filter_values[metric_name] = val
                    with sub_cols[1]:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("X", key=f"remove_{metric_name}", help=f"Quitar {metric_name}"):
                            st.session_state.screener_active_filters.remove(metric_name)
                            st.rerun()

        # Sector & country filters (separate from dynamic metrics)
        st.markdown("---")
        fc9, fc10 = st.columns(2)
        sector_filter = fc9.multiselect(
            "Filtrar por Sector",
            ["Technology", "Healthcare", "Financial Services", "Energy",
             "Consumer Cyclical", "Consumer Defensive", "Industrials",
             "Basic Materials", "Communication Services", "Real Estate", "Utilities"],
            default=[],
            key="yf_sector_filter",
        )
        country_filter = fc10.text_input(
            "Filtrar por Pais", value="", placeholder="ej: United States",
            key="yf_country_filter",
        )

    if st.button("Escanear mercado", type="primary"):
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
        if not tickers:
            st.warning("Ingresa al menos un ticker.")
            return

        with st.spinner(f"Escaneando {len(tickers)} acciones con procesamiento paralelo..."):
            results = []
            progress = st.progress(0)
            
            import concurrent.futures

            def _process_ticker(ticker):
                try:
                    tk = yf.Ticker(ticker)
                    info = tk.info
                    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
                        return None

                    price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                    sector = info.get("sector", "")
                    country = info.get("country", "")
                    name = info.get("shortName", ticker)

                    passed = True
                    for metric_name, (slider_lo, slider_hi) in filter_values.items():
                        metric = AVAILABLE_METRICS[metric_name]
                        yf_key = metric["key"]
                        scale = metric.get("scale", 1)

                        if metric.get("computed") and yf_key == "fiftyTwoWeekHigh_pct":
                            high52 = info.get("fiftyTwoWeekHigh")
                            if high52 and high52 > 0:
                                raw_val = ((price - high52) / high52) * 100
                            else:
                                raw_val = None
                        else:
                            raw_val = info.get(yf_key)

                        if raw_val is None:
                            continue

                        if yf_key in ("marketCap", "averageVolume"):
                            display_val = raw_val / scale
                        elif scale != 1:
                            display_val = raw_val * scale
                        else:
                            display_val = raw_val

                        if display_val < slider_lo or display_val > slider_hi:
                            passed = False
                            break

                    if not passed:
                        return None

                    pe = info.get("trailingPE")
                    pe_fwd = info.get("forwardPE")
                    roe = (info.get("returnOnEquity") or 0) * 100
                    margin = (info.get("profitMargins") or 0) * 100
                    mcap = info.get("marketCap", 0)
                    de = info.get("debtToEquity") or 0
                    div_y = (info.get("dividendYield") or 0) * 100
                    peg = info.get("pegRatio")
                    beta = info.get("beta")
                    rev_growth = (info.get("revenueGrowth") or 0) * 100
                    earn_growth = (info.get("earningsGrowth") or 0) * 100
                    avg_volume = info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0

                    from core.scoring import get_full_analysis
                    finterm_score = get_full_analysis(ticker, info, skip_sentiment=True)

                    return {
                        "Ticker": ticker, "Empresa": name[:25], "Sector": sector,
                        "Pais": country, "Precio": price, "P/E": pe, "P/E Fwd": pe_fwd,
                        "ROE %": round(roe, 1), "Margen %": round(margin, 1),
                        "D/E": round(de, 2), "PEG": peg, "Beta": beta,
                        "Div %": round(div_y, 2), "Crec Rev %": round(rev_growth, 1),
                        "Crec Earn %": round(earn_growth, 1),
                        "Mkt Cap": mcap, "Vol Prom": avg_volume, 
                        "Score": finterm_score["Total"], "Quant": finterm_score["Total"]
                    }
                except Exception:
                    return None

            completed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_ticker = {executor.submit(_process_ticker, t): t for t in tickers}
                for future in concurrent.futures.as_completed(future_to_ticker):
                    completed += 1
                    progress.progress(completed / len(tickers))
                    res = future.result()
                    if res:
                        results.append(res)

            progress.empty()

        # ── Apply sector & country filters ──
        if results and sector_filter:
            results = [r for r in results if r.get("Sector", "") in sector_filter]
        if results and country_filter.strip():
            cf_lower = country_filter.strip().lower()
            results = [r for r in results if cf_lower in r.get("Pais", "").lower()]

        if not results:
            st.warning("Ninguna accion paso los filtros. Intenta con criterios mas amplios.")
            return

        df = pd.DataFrame(results).sort_values("Score", ascending=False)

        # ── QUANT SCORE (Ya calculado via core.scoring en _process_ticker) ──
        # Aquí eliminamos el bloque de rankeo antiguo porque Finterm Light 
        # nos provee 'Total' absoluto ya calculado basándose en matemáticas financieras reales.

        df = df.sort_values("Quant", ascending=False, na_position="last")
        st.session_state["screener_results"] = df

        # ── RESULTS ──
    if "screener_results" in st.session_state:
        df = st.session_state["screener_results"]

        st.markdown("<div class='sec-title'>Resultados del Screener</div>", unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)
        with k1:
            vc.render_metric_card("Acciones encontradas", str(len(df)), subtitle="Cumplen criterios")
        
        avg_pe = df["P/E"].dropna().mean()
        with k2:
            vc.render_metric_card("P/E Promedio", f"{avg_pe:.1f}x" if pd.notna(avg_pe) else "--", subtitle="Grupo filtrado")
            
        avg_roe = df["ROE %"].mean()
        with k3:
            vc.render_metric_card("ROE Promedio", f"{avg_roe:.1f}%", subtitle="Rentabilidad media")

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

        # Piotroski F-Score color
        def piotroski_color(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "color:#475569"
            if v >= 7:
                return "background-color: rgba(52,211,153,0.2); color: #34d399; font-weight: 700"
            elif v >= 4:
                return "background-color: rgba(251,191,36,0.15); color: #fbbf24"
            return "background-color: rgba(248,113,113,0.15); color: #f87171"

        # Altman Z-Score color
        def altman_color(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "color:#475569"
            if v >= 3.0:
                return "background-color: rgba(52,211,153,0.2); color: #34d399; font-weight: 700"
            elif v >= 1.8:
                return "background-color: rgba(251,191,36,0.15); color: #fbbf24"
            return "background-color: rgba(248,113,113,0.15); color: #f87171"

        display_cols = ["Ticker", "Empresa", "Sector", "Pais", "Precio", "P/E", "P/E Fwd",
                        "ROE %", "Margen %", "D/E", "PEG", "Beta", "Div %", "Crec Rev %",
                        "Vol Prom", "Score", "Quant",
                        "ROIC %", "ROCE %", "Piotroski", "Altman Z", "SY %"]
        available_cols = [c for c in display_cols if c in df.columns]
        df_show = df[available_cols].copy()

        # ── STOCK CARDS UI REDESIGN ──
        st.markdown("<br>", unsafe_allow_html=True)
        
        top_n_cards = 15
        df_cards = df_show.head(top_n_cards)

        st.markdown("<div class='sec-title'>Top Oportunidades Identificadas</div>", unsafe_allow_html=True)
        
        cols_per_row = 3
        for i in range(0, len(df_cards), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(df_cards):
                    row = df_cards.iloc[i + j]
                    
                    t_tick = row["Ticker"]
                    t_name = row["Empresa"]
                    t_pe = row.get("P/E", "--")
                    t_pe = f"{t_pe:.1f}x" if pd.notna(t_pe) else "--"
                    
                    t_roe = row.get("ROE %", "--")
                    t_roe = f"{t_roe:.1f}%" if pd.notna(t_roe) else "--"
                    roe_color = "#34d399" if pd.notna(row.get("ROE %")) and row["ROE %"] > 15 else ("#f87171" if pd.notna(row.get("ROE %")) and row["ROE %"] < 5 else "#94a3b8")
                    
                    t_mar = row.get("Margen %", "--")
                    t_mar = f"{t_mar:.1f}%" if pd.notna(t_mar) else "--"
                    mar_color = "#34d399" if pd.notna(row.get("Margen %")) and row["Margen %"] > 15 else ("#f87171" if pd.notna(row.get("Margen %")) and row["Margen %"] < 5 else "#94a3b8")
                    
                    t_score = row.get("Score", 0)
                    t_quant = row.get("Quant", 50)
                    q_color = "#34d399" if pd.notna(t_quant) and t_quant > 70 else ("#fbbf24" if pd.notna(t_quant) and t_quant >= 40 else "#f87171")
                    
                    # New Metrics for Cards (Piotroski & Altman Z)
                    t_pio = row.get("Piotroski", "--")
                    try:
                        t_pio_val = float(t_pio) if pd.notna(t_pio) else 0
                    except (ValueError, TypeError):
                        t_pio_val = 0
                    pio_color = "#34d399" if t_pio_val >= 7 else ("#fbbf24" if t_pio_val >= 4 else "#f87171")
                    
                    t_alt = row.get("Altman Z", "--")
                    try:
                        t_alt_val = float(t_alt) if pd.notna(t_alt) else 0.0
                    except (ValueError, TypeError):
                        t_alt_val = 0.0
                    alt_color = "#34d399" if t_alt_val >= 3.0 else ("#fbbf24" if t_alt_val >= 1.8 else "#f87171")

                    with col:
                        # Card HTML
                        st.markdown(textwrap.dedent(f"""
                        <div style='background:linear-gradient(145deg, #111827, #1f2937); border: 1px solid #374151; border-radius: 12px; padding: 16px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>
                            <div style='display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid #374151; padding-bottom: 8px; margin-bottom: 12px;'>
                                <div>
                                    <span style='font-size: 22px; font-weight: 800; color: #60A5FA; letter-spacing: 0.5px;'>{t_tick}</span>
                                    <div style='font-size: 11px; color: #9ca3af; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; max-width: 150px;'>{t_name}</div>
                                </div>
                                <div style='background: {q_color}22; border: 1px solid {q_color}55; padding: 4px 10px; border-radius: 8px; text-align: center;'>
                                    <div style='font-size: 9px; color: {q_color}; font-weight: bold; letter-spacing: 0.5px; opacity: 0.8;'>QUANT</div>
                                    <div style='font-size: 18px; color: {q_color}; font-weight: 800;'>{int(t_quant) if pd.notna(t_quant) else 50}</div>
                                </div>
                            </div>
                            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;'>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>P/E Ratio</div>
                                    <div style='font-size: 15px; color: #e5e7eb; font-weight: 700;'>{t_pe}</div>
                                </div>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>Precio</div>
                                    <div style='font-size: 15px; color: #e5e7eb; font-weight: 700;'>${row.get("Precio", 0):.2f}</div>
                                </div>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>Margen Neto</div>
                                    <div style='font-size: 15px; color: {mar_color}; font-weight: 700;'>{t_mar}</div>
                                </div>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>ROE Promedio</div>
                                    <div style='font-size: 15px; color: {roe_color}; font-weight: 700;'>{t_roe}</div>
                                </div>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>Piotroski</div>
                                    <div style='font-size: 15px; color: {pio_color}; font-weight: 700;'>{t_pio}</div>
                                </div>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>Altman Z</div>
                                    <div style='font-size: 15px; color: {alt_color}; font-weight: 700;'>{f"{t_alt:.2f}" if isinstance(t_alt, float) else t_alt}</div>
                                </div>
                            </div>
                        </div>
                        """), unsafe_allow_html=True)
                        
                        # Acciones Button Group
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("➕ Watch", key=f"add_{t_tick}", help=f"Agregar {t_tick} a Watchlist", use_container_width=True):
                                db.add_ticker(t_tick, 0, row.get("Precio", 0), row.get("Sector", ""), "Desde screener (Card)")
                                st.success("Añadido!")
                        with b2:
                            if st.button("🔍 Ver Detalle", key=f"analyze_{t_tick}", help=f"Análisis fundamental de {t_tick}", type="primary", use_container_width=True):
                                st.session_state["active_ticker"] = t_tick
                                st.toast(f"{t_tick} marcado activo. Navega a Analizador.")

        if len(df_show) > top_n_cards:
            with st.expander(f"Ver {len(df_show) - top_n_cards} resultados adicionales en tabla"):
                # ── EXPORT RESULTS ────────────────────────────────────────────────────────
                from utils import export_utils
                export_utils.render_export_buttons(df_show.iloc[top_n_cards:], file_prefix="screener_results")

                st.dataframe(
                    df_show.iloc[top_n_cards:].style.map(score_color, subset=["Score"]).map(quant_color, subset=["Quant"]).format({"Precio": "${:.2f}", "P/E": "{:.1f}", "P/E Fwd": "{:.1f}",
                                "D/E": "{:.2f}", "PEG": "{:.2f}", "Beta": "{:.2f}", "Div %": "{:.2f}%"}, na_rep="--"),
                    use_container_width=True, hide_index=True
                )


        # ── COMPARISON CHARTS ──
        st.markdown("<div class='sec-title'>Comparacion Visual</div>", unsafe_allow_html=True)
        vc1, vc2 = st.columns(2)

        with vc1:
            fig_pe = go.Figure()
            fig_pe.add_trace(go.Bar(
                x=df["Ticker"], y=df["P/E"].fillna(0),
                marker_color=["#34d399" if (v or 99) < 20 else "#fbbf24" if (v or 99) < 30 else "#f87171"
                               for v in df["P/E"]],
                text=[f"{v:.1f}" if pd.notna(v) else "--" for v in df["P/E"]],
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
            "El paquete `finvizfinance` no esta instalado. "
            "Instalalo con: `pip install finvizfinance`"
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
                st.warning("Finviz no devolvio resultados para estos filtros.")
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
                kpi("P/E Promedio", f"{avg_pe:.1f}x" if pd.notna(avg_pe) else "--", "", "purple"),
                unsafe_allow_html=True,
            )
        else:
            k2.markdown(kpi("P/E Promedio", "--", "", "purple"), unsafe_allow_html=True)

        if "Price" in df.columns:
            price_col = pd.to_numeric(df["Price"], errors="coerce")
            avg_price = price_col.dropna().mean()
            k3.markdown(
                kpi("Precio Promedio", f"${avg_price:.2f}" if pd.notna(avg_price) else "--", "", "green"),
                unsafe_allow_html=True,
            )
        else:
            k3.markdown(kpi("Precio Promedio", "--", "", "green"), unsafe_allow_html=True)

        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", help="Símbolo del activo", width="small"),
                "Price": st.column_config.NumberColumn("Precio", format="$%.2f"),
                "Change": st.column_config.TextColumn("Cambio"),
            }
        )

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
                    st.info("No hay datos numericos de P/E para generar el heatmap.")
            except Exception as e:
                st.warning(f"No se pudo generar el heatmap: {e}")


# ── Top 100 S&P 500 by market cap, organized by 11 GICS sectors ──
HEATMAP_TICKERS = {
    "Technology": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "AMD", "CSCO", "INTC", "IBM", "QCOM", "TXN", "NOW", "INTU"],
    "Communication": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "TMUS", "VZ", "T", "EA", "WBD"],
    "Consumer Disc.": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "MAR"],
    "Consumer Staples": ["WMT", "PG", "COST", "KO", "PEP", "PM", "MO", "CL", "MDLZ", "KHC"],
    "Healthcare": ["UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD", "ISRG", "CVS", "ELV"],
    "Financials": ["BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "SPGI", "BLK", "AXP", "SCHW", "C", "CB"],
    "Industrials": ["GE", "CAT", "RTX", "HON", "UNP", "BA", "DE", "LMT", "UPS", "ADP", "GD", "MMM", "ITW"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "WEC", "ES"],
    "Real Estate": ["PLD", "AMT", "EQIX", "CCI", "PSA", "SPG", "O", "WELL", "DLR", "AVB"],
    "Materials": ["LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "DD", "VMC", "MLM"],
}

# ── Global indices & ETFs organized by region ──
GLOBAL_INDICES = {
    "US": {
        "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "Dow Jones": "^DJI",
        "Russell 2000": "^RUT", "S&P MidCap": "^MID", "VIX": "^VIX",
    },
    "Europa": {
        "FTSE 100": "^FTSE", "DAX": "^GDAXI", "CAC 40": "^FCHI",
        "Euro Stoxx 50": "^STOXX50E", "IBEX 35": "^IBEX",
    },
    "Asia": {
        "Nikkei 225": "^N225", "Hang Seng": "^HSI", "Shanghai": "000001.SS",
        "KOSPI": "^KS11", "Sensex": "^BSESN",
    },
    "Americas": {
        "Bovespa": "^BVSP", "S&P/TSX": "^GSPTSE", "IPC Mexico": "^MXX",
    },
    "ETFs Populares": {
        "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM",
        "EEM": "EEM", "GLD": "GLD", "TLT": "TLT",
    },
}


def _render_sector_heatmap():
    """FinViz-style sector heatmap using treemap colored by daily change %."""
    try:
        st.markdown("<div class='sec-title'>Sector Heatmap -- Top 100 S&P 500 -- Cambio Diario %</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                    border-radius:12px;padding:14px;margin-bottom:16px;color:#94a3b8;font-size:12px;'>
          Mapa de calor estilo FinViz con las <b>Top 100 acciones del S&amp;P 500</b> organizadas por los 11 sectores GICS.
          El tamano representa la capitalizacion de mercado relativa.
          El color indica el cambio porcentual del dia: <span style='color:#34d399'>verde = positivo</span>,
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

            with st.spinner(f"Descargando datos de {len(all_tickers)} acciones..."):
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
                height=650,
                title=dict(text="Sector Heatmap -- Top 100 S&P 500 -- Cambio Diario", font=dict(color="#94a3b8", size=14), x=0.5),
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


def _render_global_indices():
    """Global indices monitor with multi-period performance."""
    try:
        st.markdown("<div class='sec-title'>Indices Globales -- Monitor en Tiempo Real</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                    border-radius:12px;padding:14px;margin-bottom:16px;color:#94a3b8;font-size:12px;'>
          Monitor de indices bursatiles globales y ETFs populares.
          Cambios calculados sobre precios de cierre. <span style='color:#34d399'>Verde = positivo</span>,
          <span style='color:#f87171'>Rojo = negativo</span>.
        </div>""", unsafe_allow_html=True)

        if st.button("Cargar Indices Globales", type="primary", key="indices_btn"):
            from datetime import datetime

            all_symbols = {}
            symbol_region = {}
            for region, indices in GLOBAL_INDICES.items():
                for name, symbol in indices.items():
                    all_symbols[name] = symbol
                    symbol_region[name] = region

            with st.spinner(f"Descargando datos de {len(all_symbols)} indices..."):
                rows = []
                for name, symbol in all_symbols.items():
                    try:
                        tk = yf.Ticker(symbol)
                        hist = tk.history(period="6mo")
                        if hist.empty or len(hist) < 2:
                            continue

                        current = hist["Close"].iloc[-1]
                        prev_close = hist["Close"].iloc[-2]
                        daily_chg = ((current - prev_close) / prev_close * 100) if prev_close else 0

                        # 1W change
                        week_ago_idx = max(0, len(hist) - 6)
                        week_price = hist["Close"].iloc[week_ago_idx]
                        week_chg = ((current - week_price) / week_price * 100) if week_price else 0

                        # 1M change
                        month_ago_idx = max(0, len(hist) - 22)
                        month_price = hist["Close"].iloc[month_ago_idx]
                        month_chg = ((current - month_price) / month_price * 100) if month_price else 0

                        # YTD change
                        current_year = datetime.now().year
                        ytd_data = hist[hist.index.year == current_year]
                        if len(ytd_data) > 1:
                            ytd_start = ytd_data["Close"].iloc[0]
                            ytd_chg = ((current - ytd_start) / ytd_start * 100) if ytd_start else 0
                        else:
                            ytd_chg = 0

                        rows.append({
                            "Region": symbol_region[name],
                            "Indice": name,
                            "Simbolo": symbol,
                            "Precio": round(current, 2),
                            "Dia %": round(daily_chg, 2),
                            "1S %": round(week_chg, 2),
                            "1M %": round(month_chg, 2),
                            "YTD %": round(ytd_chg, 2),
                        })
                    except Exception:
                        continue

            if not rows:
                st.warning("No se pudieron obtener datos de los indices.")
                return

            idx_df = pd.DataFrame(rows)
            st.session_state["global_indices_df"] = idx_df

        if "global_indices_df" not in st.session_state:
            return

        idx_df = st.session_state["global_indices_df"]

        def _chg_color(v):
            if isinstance(v, (int, float)) and not pd.isna(v):
                if v > 0:
                    return "background-color: rgba(52,211,153,0.12); color: #34d399; font-weight: 600"
                elif v < 0:
                    return "background-color: rgba(248,113,113,0.12); color: #f87171; font-weight: 600"
            return "color: #64748b"

        chg_cols = ["Dia %", "1S %", "1M %", "YTD %"]

        for region in ["US", "Europa", "Asia", "Americas", "ETFs Populares"]:
            region_df = idx_df[idx_df["Region"] == region].copy()
            if region_df.empty:
                continue

            region_labels = {
                "US": "US",
                "Europa": "Europa",
                "Asia": "Asia-Pacifico",
                "Americas": "Latinoamerica & Canada",
                "ETFs Populares": "ETFs Populares",
            }
            label = region_labels.get(region, region)
            st.markdown(
                f"<div style='margin:18px 0 8px 0;font-size:16px;font-weight:700;color:#e2e8f0;'>"
                f"{label}</div>",
                unsafe_allow_html=True,
            )

            display_df = region_df[["Indice", "Precio", "Dia %", "1S %", "1M %", "YTD %"]].copy()
            styled = display_df.style.map(_chg_color, subset=chg_cols).format({
                "Precio": "{:,.2f}",
                "Dia %": "{:+.2f}%",
                "1S %": "{:+.2f}%",
                "1M %": "{:+.2f}%",
                "YTD %": "{:+.2f}%",
            })
            st.dataframe(styled, use_container_width=True, hide_index=True)

        # Summary bar chart: YTD performance
        st.markdown("<div class='sec-title'>Rendimiento YTD -- Todos los Indices</div>", unsafe_allow_html=True)
        chart_df = idx_df.sort_values("YTD %", ascending=True).copy()
        colors = ["#34d399" if v >= 0 else "#f87171" for v in chart_df["YTD %"]]
        fig_ytd = go.Figure()
        fig_ytd.add_trace(go.Bar(
            y=chart_df["Indice"],
            x=chart_df["YTD %"],
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.1f}%" for v in chart_df["YTD %"]],
            textposition="outside",
            textfont=dict(color="#94a3b8", size=10),
        ))
        fig_ytd.update_layout(
            **dark_layout(
                height=max(400, len(chart_df) * 28),
                title=dict(text="YTD Performance (%)", font=dict(color="#94a3b8", size=14), x=0.5),
                showlegend=False,
                xaxis=dict(title="YTD %", ticksuffix="%"),
            )
        )
        st.plotly_chart(fig_ytd, use_container_width=True)

    except Exception as e:
        st.error(f"Error al cargar indices globales: {e}")


def _render_security_finder():
    """Advanced security finder -- search by company name or partial ticker."""
    try:
        st.markdown("<div class='sec-title'>Buscador de Acciones por Nombre</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                    border-radius:12px;padding:14px;margin-bottom:16px;color:#94a3b8;font-size:12px;'>
          Busca acciones por nombre de empresa o ticker parcial. Los resultados se obtienen de yfinance.
        </div>""", unsafe_allow_html=True)

        search_query = st.text_input("Nombre de empresa o ticker",
                                      placeholder="Ej: Apple, Microsoft, Tesla, NVDA...",
                                      key="finder_query")

        # Common tickers lookup for name-based search
        COMPANY_LOOKUP = {
            "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
            "amazon": "AMZN", "meta": "META", "facebook": "META", "tesla": "TSLA",
            "nvidia": "NVDA", "netflix": "NFLX", "disney": "DIS", "intel": "INTC",
            "amd": "AMD", "salesforce": "CRM", "adobe": "ADBE", "oracle": "ORCL",
            "ibm": "IBM", "cisco": "CSCO", "qualcomm": "QCOM", "paypal": "PYPL",
            "shopify": "SHOP", "uber": "UBER", "airbnb": "ABNB", "spotify": "SPOT",
            "coca cola": "KO", "coca-cola": "KO", "pepsi": "PEP", "pepsico": "PEP",
            "walmart": "WMT", "costco": "COST", "nike": "NKE", "starbucks": "SBUX",
            "mcdonalds": "MCD", "procter": "PG", "johnson": "JNJ",
            "jpmorgan": "JPM", "jp morgan": "JPM", "goldman": "GS", "goldman sachs": "GS",
            "bank of america": "BAC", "visa": "V", "mastercard": "MA",
            "exxon": "XOM", "chevron": "CVX", "pfizer": "PFE", "moderna": "MRNA",
            "berkshire": "BRK-B", "boeing": "BA", "caterpillar": "CAT",
            "palantir": "PLTR", "snowflake": "SNOW", "crowdstrike": "CRWD",
            "broadcom": "AVGO", "lilly": "LLY", "eli lilly": "LLY",
            "unitedhealth": "UNH", "home depot": "HD", "target": "TGT",
        }

        if search_query and st.button("Buscar", type="primary", key="finder_btn"):
            query_lower = search_query.strip().lower()
            candidates = []

            # First check direct ticker
            candidates.append(search_query.strip().upper())

            # Check name lookup
            for name, ticker_val in COMPANY_LOOKUP.items():
                if query_lower in name or name in query_lower:
                    if ticker_val not in candidates:
                        candidates.append(ticker_val)

            # Also try as direct ticker (uppercase)
            if len(candidates) <= 1:
                # Try common suffixes for partial matches
                for name, ticker_val in COMPANY_LOOKUP.items():
                    if query_lower[:3] in name[:3]:
                        if ticker_val not in candidates:
                            candidates.append(ticker_val)

            candidates = candidates[:10]  # Limit

            with st.spinner(f"Buscando {len(candidates)} posibles coincidencias..."):
                results = []
                for sym in candidates:
                    try:
                        tk = yf.Ticker(sym)
                        info = tk.info
                        name = info.get("shortName") or info.get("longName", "")
                        if not name and not info.get("currentPrice"):
                            continue
                        results.append({
                            "Ticker": sym,
                            "Empresa": (name or sym)[:40],
                            "Sector": info.get("sector", "--"),
                            "Industria": (info.get("industry", "--") or "--")[:30],
                            "Mkt Cap": info.get("marketCap", 0),
                            "Precio": info.get("currentPrice") or info.get("regularMarketPrice", 0),
                            "P/E": info.get("trailingPE"),
                            "Div %": round((info.get("dividendYield") or 0) * 100, 2),
                        })
                    except Exception:
                        continue

            if results:
                res_df = pd.DataFrame(results)

                st.markdown(f"**{len(results)} resultado(s) encontrado(s)**")
                
                from utils import export_utils
                export_utils.render_export_buttons(res_df, file_prefix="finder_results")

                st.dataframe(
                    res_df.style.format({
                        "Precio": "${:.2f}",
                        "P/E": "{:.1f}",
                        "Div %": "{:.2f}%",
                        "Mkt Cap": lambda v: f"${v/1e9:.1f}B" if v and v > 1e9
                                   else (f"${v/1e6:.0f}M" if v and v > 1e6 else "--"),
                    }, na_rep="--"),
                    use_container_width=True, hide_index=True,
                )

                # Set active ticker
                finder_select = st.selectbox(
                    "Seleccionar ticker activo",
                    [""] + [r["Ticker"] for r in results],
                    key="finder_select",
                )
                if finder_select:
                    import streamlit as _st
                    _st.session_state.active_ticker = finder_select
                    st.success(f"Ticker activo: {finder_select}")

                # Add to watchlist
                finder_add = st.multiselect(
                    "Agregar a Watchlist",
                    [r["Ticker"] for r in results],
                    key="finder_add_wl",
                )
                if st.button("Agregar a Watchlist", key="finder_add_btn") and finder_add:
                    for t in finder_add:
                        row = [r for r in results if r["Ticker"] == t][0]
                        db.add_ticker(t, 0, row["Precio"], row.get("Sector", ""), "Desde buscador")
                    st.success(f"{len(finder_add)} ticker(s) agregado(s) a la watchlist.")
            else:
                st.warning("No se encontraron resultados. Intenta con otro nombre o ticker.")

    except Exception as e:
        st.warning(f"Error en el buscador: {e}")


def _render_earnings_calendar():
    """Earnings calendar for S&P 500 and watchlist tickers."""
    try:
        st.markdown("### Calendario de Earnings — S&P 500")
        st.markdown("Proximos reportes de resultados con estimaciones de analistas")

        # Use HEATMAP_TICKERS as source
        all_tickers = []
        for sector, tickers in HEATMAP_TICKERS.items():
            for t in tickers:
                all_tickers.append(t)

        # Add watchlist tickers
        try:
            wl = db.get_tickers()
            all_tickers = list(set(all_tickers + wl))
        except:
            pass

        if st.button("Cargar Calendario de Earnings", key="load_earnings_cal"):
            progress = st.progress(0)
            earnings_data = []

            for i, t in enumerate(all_tickers):
                progress.progress((i + 1) / len(all_tickers))
                try:
                    tk = yf.Ticker(t)
                    info = tk.info

                    # Get earnings date from calendar
                    cal = tk.calendar
                    earn_date = None
                    if isinstance(cal, dict) and "Earnings Date" in cal:
                        dates = cal["Earnings Date"]
                        if dates:
                            earn_date = dates[0] if isinstance(dates, list) else dates
                    elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
                        earn_date = cal.loc["Earnings Date"].iloc[0]

                    if earn_date is None:
                        continue

                    # Get earnings estimates
                    eps_trailing = info.get("trailingEps", None)
                    eps_forward = info.get("forwardEps", None)

                    earnings_data.append({
                        "Fecha": earn_date,
                        "Ticker": t,
                        "Empresa": (info.get("shortName") or t)[:25],
                        "Sector": info.get("sector", "N/A"),
                        "Market Cap": info.get("marketCap", 0),
                        "EPS Trailing": eps_trailing,
                        "EPS Forward": eps_forward,
                        "Precio": info.get("currentPrice") or info.get("regularMarketPrice", 0),
                    })
                except:
                    continue

            progress.empty()

            if earnings_data:
                df = pd.DataFrame(earnings_data)
                df["Fecha"] = pd.to_datetime(df["Fecha"])
                df = df.sort_values("Fecha")
                st.session_state["earnings_calendar_df"] = df
            else:
                st.info("No se encontraron datos de earnings")

        # Display results from session state
        if "earnings_calendar_df" in st.session_state:
            df = st.session_state["earnings_calendar_df"]

            # Filter: next 60 days
            from datetime import datetime, timedelta
            today = datetime.now()
            df_upcoming = df[(df["Fecha"] >= today) & (df["Fecha"] <= today + timedelta(days=60))]

            # KPIs
            this_week = df[(df["Fecha"] >= today) & (df["Fecha"] <= today + timedelta(days=7))]
            next_week = df[(df["Fecha"] > today + timedelta(days=7)) & (df["Fecha"] <= today + timedelta(days=14))]

            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(kpi("Esta Semana", str(len(this_week)), "empresas", "blue"), unsafe_allow_html=True)
            k2.markdown(kpi("Proxima Semana", str(len(next_week)), "empresas", "purple"), unsafe_allow_html=True)
            k3.markdown(kpi("Proximo 60D", str(len(df_upcoming)), "reportes", "green"), unsafe_allow_html=True)
            if not df_upcoming.empty:
                next_earn = df_upcoming.iloc[0]
                k4.markdown(kpi("Proximo", next_earn["Ticker"], str(next_earn["Fecha"].strftime("%d %b")), "red"), unsafe_allow_html=True)

            # Sector filter
            sectors = df_upcoming["Sector"].unique().tolist()
            sel_sectors = st.multiselect("Filtrar por sector", sectors, default=sectors, key="earn_sector_filter")
            df_show = df_upcoming[df_upcoming["Sector"].isin(sel_sectors)] if sel_sectors else df_upcoming

            # Display table
            display_df = df_show[["Fecha", "Ticker", "Empresa", "Sector", "Precio", "EPS Trailing", "EPS Forward"]].copy()
            display_df["Fecha"] = display_df["Fecha"].dt.strftime("%Y-%m-%d")
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # Timeline scatter chart
            try:
                fig = go.Figure()
                for sector in df_show["Sector"].unique():
                    sec_df = df_show[df_show["Sector"] == sector]
                    fig.add_trace(go.Scatter(
                        x=sec_df["Fecha"], y=sec_df["Sector"],
                        mode="markers+text", text=sec_df["Ticker"],
                        textposition="top center", textfont=dict(size=8, color="#94a3b8"),
                        marker=dict(size=10 + sec_df["Market Cap"].clip(0, 3e12) / 3e11),
                        name=sector,
                    ))
                fig.update_layout(**dark_layout(height=400, showlegend=False,
                    title=dict(text="Timeline de Earnings", font=dict(color="#94a3b8"))))
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass

    except Exception as e:
        st.error(f"Error en el calendario de earnings: {e}")


def _render_fund_portfolios():
    """Institutional fund portfolios from 13F filings."""
    try:
        from fund_data import FUND_PORTFOLIOS

        st.markdown("### Fondos Institucionales — Portafolios 13F")
        st.markdown(
            "<span style='color:#94a3b8;font-size:13px;'>"
            "Holdings de los fondos de inversion mas influyentes del mundo</span>",
            unsafe_allow_html=True,
        )

        fund_names = list(FUND_PORTFOLIOS.keys())
        selected = st.selectbox("Seleccionar Fondo", fund_names, key="fund_select")
        fund = FUND_PORTFOLIOS[selected]

        # Fund info card
        st.markdown(
            f"<div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:8px;"
            f"padding:16px;margin:8px 0;'>"
            f"<span style='color:#3b82f6;font-size:18px;font-weight:700;'>{selected}</span><br>"
            f"<span style='color:#94a3b8;'>AUM: {fund['aum']} | Estrategia: {fund['strategy']}</span><br>"
            f"<span style='color:#475569;font-size:11px;'>Datos: {fund['last_updated']}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Holdings table
        holdings = fund["holdings"]
        df = pd.DataFrame(holdings)

        # Style weight column
        def weight_color(v):
            if v >= 10:
                return "background-color: rgba(52,211,153,0.2); color: #34d399; font-weight: 700"
            if v >= 5:
                return "background-color: rgba(96,165,250,0.15); color: #60a5fa"
            return "color: #94a3b8"

        styled = df.style.map(weight_color, subset=["weight"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Charts: pie + bar side by side
        c1, c2 = st.columns(2)
        with c1:
            sector_agg = df.groupby("sector")["weight"].sum().reset_index()
            fig_pie = px.pie(
                sector_agg,
                values="weight",
                names="sector",
                color_discrete_sequence=[
                    "#3b82f6", "#60a5fa", "#34d399", "#fbbf24",
                    "#f87171", "#a78bfa", "#f472b6", "#38bdf8",
                ],
            )
            fig_pie.update_layout(
                **dark_layout(height=350),
                showlegend=True,
            )
            fig_pie.update_traces(textinfo="percent+label", textfont_size=10)
            st.plotly_chart(fig_pie, use_container_width=True)

        with c2:
            top10 = df.nlargest(10, "weight")
            fig_bar = go.Figure(
                go.Bar(
                    y=top10["ticker"],
                    x=top10["weight"],
                    orientation="h",
                    marker_color="#3b82f6",
                    text=[f"{w:.1f}%" for w in top10["weight"]],
                    textposition="outside",
                    textfont=dict(color="#94a3b8"),
                )
            )
            fig_bar.update_layout(
                **dark_layout(
                    height=350,
                    title=dict(text="Top 10 Holdings", font=dict(color="#94a3b8")),
                    xaxis_title="Peso %",
                )
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # Portfolio overlap
        try:
            user_tickers = db.get_tickers()
            if user_tickers:
                fund_tickers = [h["ticker"] for h in holdings]
                overlap = set(user_tickers) & set(fund_tickers)
                if overlap:
                    st.success(
                        f"**Overlap con tu portafolio:** {', '.join(sorted(overlap))} "
                        f"({len(overlap)} tickers en comun)"
                    )
                else:
                    st.info("Sin overlap con tu portafolio actual")
        except Exception:
            pass

        # SEC EDGAR link
        st.markdown(
            f"[Ver 13F completo en SEC EDGAR]"
            f"(https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={fund['cik']}&type=13F&dateb=&owner=include&count=10)"
        )

    except Exception as e:
        st.error(f"Error al cargar fondos institucionales: {e}")


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Market Screener</h1>
        <p>Filtrado fundamental - Comparacion rapida - Seleccion Value & Growth</p>
      </div>
    </div>""", unsafe_allow_html=True)

    tab_yf, tab_fvz, tab_heatmap, tab_indices, tab_finder, tab_earnings, tab_funds = st.tabs(
        ["yfinance Screener", "Finviz Screener", "Sector Heatmap",
         "Indices Globales", "Buscador Avanzado", "Earnings Calendar",
         "Fondos Institucionales"])

    with tab_yf:
        _render_yfinance_screener()

    with tab_fvz:
        _render_finviz_screener()

    with tab_heatmap:
        _render_sector_heatmap()

    with tab_indices:
        _render_global_indices()

    with tab_finder:
        _render_security_finder()

    with tab_earnings:
        _render_earnings_calendar()

    with tab_funds:
        _render_fund_portfolios()
