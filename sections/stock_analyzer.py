"""
pages/stock_analyzer.py - PDF Stock Analyzer section
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import database as db
import pdf_parser
import valuation
import report_generator
import translator
import excel_export
import ai_engine
from ui_shared import DARK, dark_layout, IDEAL, score, fmt, kpi

try:
    from finvizfinance.quote import finvizfinance as fvz_quote
except ImportError:
    fvz_quote = None

try:
    import yfinance as yf
except ImportError:
    yf = None


# ---------------------------------------------------------------------------
# TradingView Widgets Ecosystem
# ---------------------------------------------------------------------------
def _tradingview_chart(ticker: str, height: int = 550):
    """Embed TradingView Advanced Chart with drawing tools, studies, fundamentals."""
    html = f"""
    <div class="tradingview-widget-container" style="height:{height}px;width:100%;">
      <div id="tradingview_advanced" style="height:100%;width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{ticker}",
        "interval": "D",
        "timezone": "America/New_York",
        "theme": "dark",
        "style": "1",
        "locale": "es",
        "toolbar_bg": "#000000",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "details": true,
        "hotlist": true,
        "calendar": true,
        "studies": ["STD;Bollinger_Bands", "STD;MACD", "STD;RSI"],
        "show_popup_button": true,
        "popup_width": "1000",
        "popup_height": "650",
        "container_id": "tradingview_advanced",
        "backgroundColor": "rgba(0,0,0,1)",
        "gridColor": "rgba(20,20,20,0.3)"
      }});
      </script>
    </div>
    """
    components.html(html, height=height + 10)


def _tradingview_analyst_insights(ticker: str):
    """Symbol Info + Technical Analysis Gauge side by side."""
    col1, col2 = st.columns(2)
    with col1:
        html_info = f"""
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript"
            src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-info.js" async>
          {{
            "symbol": "{ticker}",
            "width": "100%",
            "locale": "es",
            "colorTheme": "dark",
            "isTransparent": true
          }}
          </script>
        </div>
        """
        components.html(html_info, height=220)
    with col2:
        html_ta = f"""
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript"
            src="https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js" async>
          {{
            "interval": "1D",
            "width": "100%",
            "isTransparent": true,
            "height": 210,
            "symbol": "{ticker}",
            "showIntervalTabs": true,
            "displayMode": "single",
            "locale": "es",
            "colorTheme": "dark"
          }}
          </script>
        </div>
        """
        components.html(html_ta, height=220)


def _tradingview_news(ticker: str):
    """Timeline widget — institutional news feed for the active ticker."""
    html_news = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript"
        src="https://s3.tradingview.com/external-embedding/embed-widget-timeline.js" async>
      {{
        "feedMode": "symbol",
        "symbol": "{ticker}",
        "isTransparent": true,
        "displayMode": "regular",
        "width": "100%",
        "height": 400,
        "colorTheme": "dark",
        "locale": "es"
      }}
      </script>
    </div>
    """
    components.html(html_news, height=410)


# ---------------------------------------------------------------------------
# Margin of Safety Card
# ---------------------------------------------------------------------------
def _margin_of_safety_card(current_price, fair_value, ticker):
    """Compara precio actual vs Fair Value. Alerta institucional si margen >= 20%."""
    if not current_price or not fair_value or fair_value <= 0:
        return
    margin = ((fair_value - current_price) / fair_value) * 100
    discount = ((fair_value - current_price) / current_price) * 100
    if margin >= 20:
        st.markdown(f"""
        <div style='background:linear-gradient(135deg, rgba(0,80,40,0.4), rgba(0,60,30,0.6));
                    border:2px solid #34d399; border-radius:14px; padding:24px;
                    text-align:center;'>
          <div style='font-size:11px;color:#34d399;text-transform:uppercase;letter-spacing:2px;
                      font-weight:700;'>⚡ OPORTUNIDAD DE COMPRA INSTITUCIONAL ⚡</div>
          <div style='font-size:36px;font-weight:800;color:#34d399;margin:8px 0;'>
            {margin:.1f}% MARGEN DE SEGURIDAD</div>
          <div style='display:flex;justify-content:center;gap:40px;margin-top:12px;'>
            <div><span style='color:#64748b;font-size:11px;'>PRECIO ACTUAL</span><br>
                 <span style='color:#f0f6ff;font-size:20px;font-weight:700;'>${current_price:,.2f}</span></div>
            <div><span style='color:#64748b;font-size:11px;'>FAIR VALUE</span><br>
                 <span style='color:#34d399;font-size:20px;font-weight:700;'>${fair_value:,.2f}</span></div>
            <div><span style='color:#64748b;font-size:11px;'>UPSIDE POTENCIAL</span><br>
                 <span style='color:#34d399;font-size:20px;font-weight:700;'>+{discount:,.1f}%</span></div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    elif margin >= 0:
        st.markdown(f"""
        <div style='background:rgba(66,32,6,0.4);border:1px solid #fbbf24;border-radius:14px;
                    padding:20px;text-align:center;'>
          <div style='font-size:11px;color:#fbbf24;text-transform:uppercase;letter-spacing:1.5px;
                      font-weight:600;'>DESCUENTO MODERADO</div>
          <div style='font-size:28px;font-weight:700;color:#fbbf24;margin:6px 0;'>
            {margin:.1f}% margen</div>
          <div style='color:#94a3b8;font-size:13px;'>
            Precio: ${current_price:,.2f} · Fair Value: ${fair_value:,.2f}</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='background:rgba(69,26,3,0.4);border:1px solid #f87171;border-radius:14px;
                    padding:20px;text-align:center;'>
          <div style='font-size:11px;color:#f87171;text-transform:uppercase;letter-spacing:1.5px;
                      font-weight:600;'>SOBREVALORADO</div>
          <div style='font-size:28px;font-weight:700;color:#f87171;margin:6px 0;'>
            {abs(margin):.1f}% sobre Fair Value</div>
          <div style='color:#94a3b8;font-size:13px;'>
            Precio: ${current_price:,.2f} · Fair Value: ${fair_value:,.2f}</div>
        </div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Snowflake Radar (Simply Wall St style)
# ---------------------------------------------------------------------------
SECTOR_PEERS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMZN", "CRM", "ADBE"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT"],
    "Financial Services": ["JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW"],
    "Financials": ["JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW"],
    "Consumer Cyclical": ["TSLA", "AMZN", "HD", "NKE", "MCD", "SBUX", "TGT", "LOW"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST", "CL", "MDLZ", "GIS"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO"],
    "Industrials": ["CAT", "HON", "UNP", "BA", "GE", "RTX", "DE", "LMT"],
    "Communication Services": ["GOOGL", "META", "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL"],
    "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "SPG", "O", "PSA", "DLR"],
    "Basic Materials": ["LIN", "APD", "SHW", "ECL", "NEM", "FCX", "NUE", "DD"],
}


def _snowflake_radar(ticker):
    """Simply Wall St style 5-axis radar: Value, Growth, Health, Dividend, Momentum."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
    except Exception:
        return

    # Score each axis 0-5
    # Value: P/E vs 25 (lower = better)
    pe = info.get("trailingPE") or info.get("forwardPE")
    value_score = max(0, min(5, 5 - (pe - 10) / 6)) if pe and pe > 0 else 2.5

    # Growth: Revenue growth %
    rev_growth = info.get("revenueGrowth", 0) or 0
    growth_score = max(0, min(5, rev_growth * 100 / 10))  # 50% growth = 5

    # Health: Current ratio + low debt
    cr = info.get("currentRatio", 1.5) or 1.5
    de = info.get("debtToEquity", 100) or 100
    health_score = max(0, min(5, (cr / 0.6) + (3 - de / 100)))

    # Dividend: yield %
    div_yield = (info.get("dividendYield") or 0) * 100
    dividend_score = max(0, min(5, div_yield / 1.0))  # 5% yield = 5

    # Momentum: 52-week return
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    low52 = info.get("fiftyTwoWeekLow") or price
    high52 = info.get("fiftyTwoWeekHigh") or price
    if high52 > low52 and price > 0:
        momentum_score = max(0, min(5, ((price - low52) / (high52 - low52)) * 5))
    else:
        momentum_score = 2.5

    categories = ["Value", "Growth", "Health", "Dividend", "Momentum"]
    scores = [value_score, growth_score, health_score, dividend_score, momentum_score]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores + [scores[0]],
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor="rgba(96,165,250,0.15)",
        line=dict(color="#60a5fa", width=2),
        marker=dict(size=6, color="#60a5fa"),
    ))
    fig.update_layout(**dark_layout(
        polar=dict(
            bgcolor="#0a0a0a",
            radialaxis=dict(visible=True, range=[0, 5], linecolor="#1a1a1a",
                            gridcolor="#1a1a1a", tickfont=dict(color="#5a6f8a", size=10)),
            angularaxis=dict(linecolor="#1a1a1a", gridcolor="#1a1a1a",
                             tickfont=dict(color="#94a3b8", size=12)),
        ),
        height=350,
        margin=dict(l=60, r=60, t=40, b=40),
    ))
    st.plotly_chart(fig, use_container_width=True)

    # Score summary
    avg_score = sum(scores) / len(scores)
    label = "EXCELENTE" if avg_score >= 3.5 else ("BUENO" if avg_score >= 2.5 else "DÉBIL")
    color = "#34d399" if avg_score >= 3.5 else ("#fbbf24" if avg_score >= 2.5 else "#f87171")
    st.markdown(
        f"<div style='text-align:center;color:{color};font-weight:700;font-size:16px;'>"
        f"{label} — {avg_score:.1f}/5.0</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Analyst Price Targets
# ---------------------------------------------------------------------------
def _analyst_price_targets(ticker):
    """Show analyst consensus price target range as a visual bar."""
    try:
        tk = yf.Ticker(ticker)
        targets = tk.analyst_price_targets
        if targets is None or (hasattr(targets, "empty") and targets.empty):
            st.info("No hay price targets de analistas disponibles.")
            return
        current = targets.get("current", 0) or 0
        low = targets.get("low", 0) or 0
        high = targets.get("high", 0) or 0
        mean = targets.get("mean", 0) or 0
        median = targets.get("median", 0) or 0
    except Exception:
        st.info("No se pudieron obtener price targets.")
        return

    if not high or not low:
        return

    price_now = current if current else mean
    bar_min = low * 0.95
    bar_max = high * 1.05
    bar_range = bar_max - bar_min if bar_max > bar_min else 1

    def pct(val):
        return max(0, min(100, ((val - bar_min) / bar_range) * 100))

    pct_low = pct(low)
    pct_high = pct(high)
    pct_mean = pct(mean)
    pct_price = pct(price_now)

    upside = ((mean - price_now) / price_now * 100) if price_now else 0
    upside_color = "#34d399" if upside >= 0 else "#f87171"

    st.markdown(f"""
    <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:12px;padding:20px;'>
      <div style='display:flex;justify-content:space-between;margin-bottom:8px;'>
        <span style='color:#94a3b8;font-size:12px;'>LOW: ${low:,.2f}</span>
        <span style='color:#94a3b8;font-size:12px;'>MEAN: ${mean:,.2f}</span>
        <span style='color:#94a3b8;font-size:12px;'>HIGH: ${high:,.2f}</span>
      </div>
      <div style='position:relative;height:32px;background:#111;border-radius:6px;overflow:visible;'>
        <!-- Range bar low-to-high -->
        <div style='position:absolute;left:{pct_low}%;width:{pct_high - pct_low}%;height:100%;
                    background:linear-gradient(90deg, #f87171, #fbbf24, #34d399);border-radius:6px;opacity:0.3;'></div>
        <!-- Mean marker -->
        <div style='position:absolute;left:{pct_mean}%;top:-4px;width:3px;height:40px;
                    background:#a78bfa;border-radius:2px;'></div>
        <!-- Current price marker -->
        <div style='position:absolute;left:{pct_price}%;top:-6px;width:14px;height:14px;
                    margin-left:-7px;top:9px;background:#60a5fa;border-radius:50%;
                    border:2px solid #fff;z-index:2;'></div>
      </div>
      <div style='display:flex;justify-content:space-between;margin-top:10px;'>
        <span style='color:#60a5fa;font-size:13px;font-weight:600;'>Precio actual: ${price_now:,.2f}</span>
        <span style='color:{upside_color};font-size:13px;font-weight:600;'>
          Upside al mean: {upside:+.1f}%</span>
      </div>
      {f"<div style='text-align:center;color:#94a3b8;font-size:11px;margin-top:6px;'>Median: ${median:,.2f}</div>" if median else ""}
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Peer Comparison Table
# ---------------------------------------------------------------------------
def _peer_comparison(ticker):
    """Compare ticker vs 5-8 sector peers on key metrics."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
    except Exception:
        st.info("No se pudo obtener información del ticker.")
        return

    sector = info.get("sector", "")
    peers_list = SECTOR_PEERS.get(sector, [])
    # Remove self and limit to 7
    peers_list = [p for p in peers_list if p.upper() != ticker.upper()][:7]

    if not peers_list:
        st.info(f"No hay peers definidos para el sector '{sector}'.")
        return

    tickers_to_fetch = [ticker.upper()] + peers_list

    rows = []
    for sym in tickers_to_fetch:
        try:
            t = yf.Ticker(sym)
            i = t.info
            rows.append({
                "Ticker": sym,
                "P/E": round(i.get("trailingPE") or 0, 1),
                "Fwd P/E": round(i.get("forwardPE") or 0, 1),
                "P/B": round(i.get("priceToBook") or 0, 2),
                "EV/EBITDA": round(i.get("enterpriseToEbitda") or 0, 1),
                "Margen Neto %": round((i.get("profitMargins") or 0) * 100, 1),
                "ROE %": round((i.get("returnOnEquity") or 0) * 100, 1),
                "Rev Growth %": round((i.get("revenueGrowth") or 0) * 100, 1),
                "Div Yield %": round((i.get("dividendYield") or 0) * 100, 2),
                "Mkt Cap (B)": round((i.get("marketCap") or 0) / 1e9, 1),
            })
        except Exception:
            continue

    if not rows:
        st.info("No se pudieron obtener datos de peers.")
        return

    df = pd.DataFrame(rows)

    # Style: highlight the main ticker row
    def highlight_main(row):
        if row["Ticker"] == ticker.upper():
            return ["background-color: rgba(96,165,250,0.12); font-weight: 700;"] * len(row)
        return [""] * len(row)

    styled = (
        df.style
        .apply(highlight_main, axis=1)
        .format(precision=1, na_rep="—")
        .set_properties(**{
            "color": "#c8d6e5",
            "background-color": "#0a0a0a",
            "border-color": "#1a1a1a",
            "font-size": "12px",
        })
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Insider Trading
# ---------------------------------------------------------------------------
def _render_insider_trading(ticker: str):
    """Show insider trading data from finvizfinance or yfinance fallback."""
    insider_df = None

    # Try finvizfinance first
    if fvz_quote is not None:
        try:
            stock = fvz_quote(ticker)
            insider_df = stock.ticker_inside_trader()
            if insider_df is not None and not insider_df.empty:
                insider_df = insider_df.head(15)
        except Exception:
            insider_df = None

    # Fallback to yfinance
    if (insider_df is None or insider_df.empty) and yf is not None:
        try:
            tk = yf.Ticker(ticker)
            insider_df = tk.insider_transactions
            if insider_df is not None and not insider_df.empty:
                insider_df = insider_df.head(15)
        except Exception:
            insider_df = None

    if insider_df is not None and not insider_df.empty:
        st.dataframe(insider_df, use_container_width=True, hide_index=True)

        # Quick summary
        cols_lower = [c.lower() for c in insider_df.columns]
        buy_count = 0
        sell_count = 0
        for _, row in insider_df.iterrows():
            for col in insider_df.columns:
                val = str(row[col]).lower()
                if "buy" in val or "purchase" in val or "compra" in val:
                    buy_count += 1
                    break
                elif "sale" in val or "sell" in val or "venta" in val:
                    sell_count += 1
                    break

        if buy_count > sell_count:
            st.success(f"🟢 Tendencia positiva: {buy_count} compras vs {sell_count} ventas de insiders")
        elif sell_count > buy_count:
            st.warning(f"🔴 Tendencia negativa: {sell_count} ventas vs {buy_count} compras de insiders")
        else:
            st.info(f"⚪ Actividad mixta: {buy_count} compras, {sell_count} ventas")
    else:
        st.info("No se encontraron datos de insider trading para este ticker.")


# ---------------------------------------------------------------------------
# Buffett/Dorsey Quality Score display
# ---------------------------------------------------------------------------
def _render_quality_score(ticker: str):
    """Display Buffett/Dorsey quality checklist with gauge + detail."""
    # Check for MOAT rating
    moat_rating = None
    thesis = db.get_investment_notes(ticker)
    if thesis:
        moat_rating = thesis.get("moat_rating")

    with st.spinner("Calculando Checklist Buffett/Dorsey…"):
        qs = valuation.compute_quality_score(ticker, moat_rating)

    if not qs or "score" not in qs:
        st.info("No se pudo calcular el quality score.")
        return

    sc = qs["score"]
    sc_color = "#34d399" if sc >= 70 else ("#fbbf24" if sc >= 40 else "#f87171")
    sc_bg = "#064e3b" if sc >= 70 else ("#422006" if sc >= 40 else "#451a03")
    label = "EXCELENTE" if sc >= 70 else ("ACEPTABLE" if sc >= 40 else "DEBIL")

    q1, q2 = st.columns([1, 2])
    with q1:
        fig_q = go.Figure(go.Indicator(
            mode="gauge+number",
            value=sc,
            number=dict(suffix="/100", font=dict(color="#f0f6ff", size=28)),
            title=dict(text="Quality Score", font=dict(color="#94a3b8", size=14)),
            gauge=dict(
                axis=dict(range=[0, 100], tickcolor="#475569",
                         tickfont=dict(color="#475569", size=10)),
                bar=dict(color=sc_color, thickness=0.7),
                bgcolor="#0a0a0a", bordercolor="#1a1a1a",
                steps=[
                    dict(range=[0, 40], color="rgba(248,113,113,0.1)"),
                    dict(range=[40, 70], color="rgba(251,191,36,0.1)"),
                    dict(range=[70, 100], color="rgba(52,211,153,0.1)"),
                ],
            )
        ))
        fig_q.update_layout(**dark_layout(height=250, margin=dict(l=20, r=20, t=50, b=10)))
        st.plotly_chart(fig_q, use_container_width=True)
        st.markdown(f"""
        <div style='text-align:center;background:{sc_bg};border:2px solid {sc_color};
                    border-radius:10px;padding:8px;'>
          <span style='color:{sc_color};font-weight:700;font-size:16px;'>{label}</span>
          <span style='color:#64748b;font-size:12px;'> — {qs['passed']}/{qs['total']} criterios</span>
        </div>""", unsafe_allow_html=True)

    with q2:
        for item in qs["details"]:
            icon = "✅" if item["passed"] else "❌"
            v = item["value"]
            if v is not None:
                if isinstance(v, float):
                    v_str = f"{v:.2f}"
                else:
                    v_str = str(v)
            else:
                v_str = "N/A"
            color = "#34d399" if item["passed"] else "#f87171"
            st.markdown(f"""<div style='display:flex;justify-content:space-between;padding:4px 8px;
                border-bottom:1px solid rgba(30,45,64,0.3);'>
              <span style='color:#94a3b8;font-size:13px;'>{icon} {item['criterion']}</span>
              <span style='color:{color};font-weight:600;font-size:13px;'>{v_str}</span>
            </div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# DCF Scenarios display
# ---------------------------------------------------------------------------
def _render_dcf_scenarios(ticker: str, parsed_data: dict = None):
    """Display DCF with 3 scenarios (Pessimistic/Base/Optimistic)."""
    with st.spinner("Calculando escenarios DCF…"):
        dcf = valuation.compute_dcf_scenarios(ticker, parsed_data)

    if not dcf or "base" not in dcf:
        st.info("No se pudieron calcular escenarios DCF (EPS ≤ 0 o datos insuficientes).")
        return

    current_price = dcf.get("current_price", 0)

    # Bar chart
    scenarios = ["pessimistic", "base", "optimistic"]
    labels = [dcf[s]["label"] for s in scenarios]
    values = [dcf[s]["fair_value"] for s in scenarios]
    colors = ["#f87171", "#60a5fa", "#34d399"]

    fig_dcf = go.Figure()
    fig_dcf.add_trace(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        text=[f"${v:,.2f}" for v in values],
        textposition="outside",
        textfont=dict(color="#94a3b8", size=12),
    ))
    if current_price > 0:
        fig_dcf.add_hline(y=current_price, line_dash="dash", line_color="#fbbf24",
                          annotation_text=f"Precio Actual: ${current_price:,.2f}",
                          annotation_font_color="#fbbf24")

    fig_dcf.update_layout(**DARK, height=350,
        title=dict(text="Fair Value — 3 Escenarios DCF", font=dict(color="#94a3b8", size=14), x=0.5),
        yaxis_title="Fair Value ($)",
        showlegend=False)
    st.plotly_chart(fig_dcf, use_container_width=True)

    # Details table
    d1, d2, d3 = st.columns(3)
    for col, key, color in [(d1, "pessimistic", "#f87171"), (d2, "base", "#60a5fa"), (d3, "optimistic", "#34d399")]:
        s = dcf[key]
        upside = ((s["fair_value"] / current_price - 1) * 100) if current_price > 0 else 0
        col.markdown(f"""
        <div class='metric-card' style='border-top:3px solid {color};'>
          <div class='mc-label'>{s['label']}</div>
          <div class='mc-value' style='color:{color};'>${s['fair_value']:,.2f}</div>
          <div style='font-size:11px;color:#64748b;'>
            Crec: {s['growth']}% · Desc: {s['discount']}% · Term: {s['terminal']}%<br>
            Potencial: <span style='color:{"#34d399" if upside > 0 else "#f87171"};font-weight:600;'>{upside:+.1f}%</span>
          </div>
        </div>""", unsafe_allow_html=True)


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Analizador de Acciones</h1>
        <p>InvestingPro PDF · Extracción inteligente · Fair Value · Métricas avanzadas</p>
      </div>
    </div>""", unsafe_allow_html=True)

    col_up, col_r = st.columns([2, 1])
    with col_up:
        uploaded = st.file_uploader("Subir informe financiero (PDF)", type=["pdf"],
                                     label_visibility="collapsed")
    with col_r:
        manual_ticker = st.text_input("Ticker de la empresa", placeholder="MSFT, AAPL, INTU…",
                                      value=st.session_state.get("active_ticker", ""))

    if uploaded:
        with st.spinner("Extrayendo datos del PDF…"):
            try:
                file_bytes = uploaded.read()
                parsed = pdf_parser.parse_financial_pdf(file_bytes)
                # ── Translate to Spanish ──
                translator.translate_parsed_data(parsed)
                flat = pdf_parser.flatten_for_db(parsed)
                is_pro = parsed.get("source") == "investingpro"

                ticker_name = manual_ticker.upper() if manual_ticker else (flat.get("ticker") or uploaded.name.replace(".pdf", ""))
                m = flat

                # ── Manual overrides ──
                with st.expander("✏️  Ajustar métricas manualmente"):
                    c1, c2, c3 = st.columns(3)
                    m["revenue"]        = c1.number_input("Ingresos ($)",        value=m.get("revenue") or 0.0, step=1e9, format="%.0f")
                    m["net_income"]     = c1.number_input("Beneficio Neto ($)",  value=m.get("net_income") or 0.0, step=1e8, format="%.0f")
                    m["total_debt"]     = c2.number_input("Deuda Total ($)",     value=m.get("total_debt") or 0.0, step=1e8, format="%.0f")
                    m["total_equity"]   = c2.number_input("Patrimonio ($)",      value=m.get("total_equity") or 0.0, step=1e8, format="%.0f")
                    m["profit_margin"]  = c3.number_input("Margen Neto (%)",     value=m.get("profit_margin") or 0.0)
                    m["revenue_growth"] = c3.number_input("Crec. Ingresos (%)",  value=m.get("revenue_growth") or 0.0)
                    m["pe_ratio"]       = c1.number_input("P/E Ratio",           value=m.get("pe_ratio") or 0.0)
                    m["roe"]            = c2.number_input("ROE (%)",             value=m.get("roe") or 0.0)
                    m["current_ratio"]  = c3.number_input("Ratio Corriente",     value=m.get("current_ratio") or 0.0)

                debt_eq = m.get("debt_equity")
                if not debt_eq and m.get("total_debt") and m.get("total_equity") and m["total_equity"] > 0:
                    debt_eq = m["total_debt"] / m["total_equity"]

                checks = [
                    ("revenue_growth", m.get("revenue_growth")),
                    ("profit_margin",  m.get("profit_margin")),
                    ("roe",            m.get("roe")),
                    ("current_ratio",  m.get("current_ratio")),
                    ("pe_ratio",       m.get("pe_ratio")),
                    ("debt_equity",    debt_eq),
                ]
                passed  = sum(1 for k, v in checks if score(k, v) is True)
                total_c = len(checks)
                pct     = passed / total_c * 100

                ring_color = "#34d399" if pct >= 70 else ("#fbbf24" if pct >= 40 else "#f87171")
                ring_bg    = "#064e3b" if pct >= 70 else ("#451a03" if pct < 40 else "#422006")

                # ── COMPANY HEADER + SCORE ──
                hc1, hc2 = st.columns([3, 1])
                with hc1:
                    company_name = flat.get("company_name") or ticker_name
                    sub_info = f"{uploaded.name}"
                    if is_pro:
                        sub_info += " · InvestingPro"
                    ki = parsed.get("key_indicators", {})
                    if ki.get("date"):
                        sub_info += f" · {ki['date']}"
                    st.markdown(f"""
                    <div style='background:linear-gradient(135deg,#0d1f35,#0a1628);border:1px solid #1e3a5f;
                                border-radius:14px;padding:24px 28px;margin-bottom:20px;'>
                      <div style='font-size:28px;font-weight:700;color:#f0f6ff;'>{company_name}</div>
                      <div style='font-size:15px;color:#60a5fa;margin-top:2px;'>{ticker_name}</div>
                      <div style='font-size:13px;color:#64748b;margin-top:4px;'>{sub_info}</div>
                    </div>""", unsafe_allow_html=True)
                with hc2:
                    st.markdown(f"""
                    <div style='background:{ring_bg};border:2px solid {ring_color};border-radius:14px;
                                padding:20px;text-align:center;margin-bottom:20px;'>
                      <div style='font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;'>Puntuacion</div>
                      <div style='font-size:44px;font-weight:800;color:{ring_color};line-height:1.1;'>{pct:.0f}%</div>
                      <div style='font-size:12px;color:#64748b;margin-top:4px;'>{passed} / {total_c} criterios</div>
                    </div>""", unsafe_allow_html=True)

                # ── TRADINGVIEW CHART ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.expander("📈 TradingView — Chart en Tiempo Real", expanded=False):
                        try:
                            _tradingview_chart(ticker_name)
                        except Exception:
                            st.info("No se pudo cargar el chart de TradingView.")

                # ── FAIR VALUE TRAFFIC LIGHT ──
                fv = None
                adv = None
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.spinner("Calculando Fair Value…"):
                        fv = valuation.compute_fair_values(ticker_name, parsed)
                    if fv.get("avg_fair_value"):
                        st.markdown("<div class='sec-title'>Fair Value & Semaforo</div>", unsafe_allow_html=True)
                        fv_cols = st.columns(4)
                        sig_colors = {"green": "#34d399", "yellow": "#fbbf24", "red": "#f87171"}
                        sig_labels = {"undervalued": "INFRAVALORADA", "fair": "VALOR JUSTO", "overvalued": "SOBREVALORADA"}
                        sig_bg = {"green": "#064e3b", "yellow": "#422006", "red": "#451a03"}
                        sc = fv["signal_color"] or "yellow"

                        fv_cols[0].markdown(kpi("Precio Actual", f"${fv['current_price']:,.2f}", "", "blue"), unsafe_allow_html=True)
                        if fv.get("pe_fair_value"):
                            fv_cols[1].markdown(kpi("FV por Multiplos", f"${fv['pe_fair_value']:,.2f}",
                                f"P/E: {fv['details'].get('pe_method',{}).get('applied_pe',''):.1f}x", "purple"), unsafe_allow_html=True)
                        if fv.get("dcf_fair_value"):
                            fv_cols[2].markdown(kpi("FV por DCF", f"${fv['dcf_fair_value']:,.2f}",
                                f"g: {fv['details'].get('dcf_method',{}).get('growth_rate',0)*100:.1f}%", "purple"), unsafe_allow_html=True)
                        fv_cols[3].markdown(f"""
                        <div style='background:{sig_bg[sc]};border:2px solid {sig_colors[sc]};border-radius:14px;
                                    padding:16px;text-align:center;'>
                          <div style='font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;'>Senal</div>
                          <div style='font-size:22px;font-weight:800;color:{sig_colors[sc]};'>{sig_labels.get(fv['signal'],'')}</div>
                          <div style='font-size:13px;color:#64748b;'>FV Prom: ${fv["avg_fair_value"]:,.2f} ({fv["upside_pct"]:+.1f}%)</div>
                        </div>""", unsafe_allow_html=True)

                # ── KEY INDICATORS (InvestingPro) ──
                if is_pro:
                    st.markdown("<div class='sec-title'>Indicadores Clave</div>", unsafe_allow_html=True)
                    ki_cols = st.columns(6)
                    ki_items = [
                        ("Precio", f"${ki.get('price',0):,.2f}" if ki.get('price') else "—", "blue"),
                        ("Market Cap", fmt(ki.get('market_cap')), "purple"),
                        ("P/E (Fwd)", f"{ki.get('pe_fwd','—')}", "blue"),
                        ("PEG", f"{ki.get('peg_ratio','—')}", "green" if (ki.get('peg_ratio') or 99) < 1 else "red"),
                        ("EV/EBITDA", f"{ki.get('ev_ebitda','—')}x", "blue"),
                        ("Beta", f"{ki.get('beta','—')}", "blue"),
                    ]
                    for col, (lbl, val, clr) in zip(ki_cols, ki_items):
                        col.markdown(kpi(lbl, val, "", clr), unsafe_allow_html=True)

                    ki_cols2 = st.columns(6)
                    ki_items2 = [
                        ("EPS Actual", f"${ki.get('eps_actual','—')}", "blue"),
                        ("EPS Est.", f"${ki.get('eps_estimate','—')}", "blue"),
                        ("FCF Yield", f"{ki.get('fcf_yield','—')}%", "green"),
                        ("Div Yield", f"{ki.get('div_yield','—')}%", "green"),
                        ("1Y Change", f"{ki.get('one_year_change','—')}%",
                         "green" if (ki.get('one_year_change') or 0) >= 0 else "red"),
                        ("Book/Share", f"${ki.get('book_per_share','—')}", "blue"),
                    ]
                    for col, (lbl, val, clr) in zip(ki_cols2, ki_items2):
                        col.markdown(kpi(lbl, val, "", clr), unsafe_allow_html=True)

                # ── ABSOLUTE FIGURES ──
                st.markdown("<div class='sec-title'>Cifras Absolutas</div>", unsafe_allow_html=True)
                fa1, fa2, fa3, fa4 = st.columns(4)
                figures = [
                    (fa1, "Ingresos Totales",   m.get("revenue"),      "blue"),
                    (fa2, "Beneficio Neto",      m.get("net_income"),   "green"),
                    (fa3, "Deuda Total",          m.get("total_debt"),   "red"),
                    (fa4, "Patrimonio",           m.get("total_equity"), "purple"),
                ]
                for col, label, val, color in figures:
                    col.markdown(kpi(label, fmt(val), "", color), unsafe_allow_html=True)

                # ── RATIO METRICS ──
                st.markdown("<div class='sec-title'>Ratios & Metricas Clave</div>", unsafe_allow_html=True)

                metrics_display = [
                    ("revenue_growth", m.get("revenue_growth"), "Crec. Ingresos",  "%",  True,  10),
                    ("profit_margin",  m.get("profit_margin"),  "Margen Neto",     "%",  True,  15),
                    ("roe",            m.get("roe"),            "ROE",             "%",  True,  15),
                    ("current_ratio",  m.get("current_ratio"),  "Ratio Corriente", "x",  True,  1.5),
                    ("pe_ratio",       m.get("pe_ratio"),       "P/E Ratio",       "x",  False, 25),
                    ("debt_equity",    debt_eq,                 "Deuda/Patrimonio","x",  False, 1.0),
                ]

                cols6 = st.columns(6)
                for col, (key, val, label, unit, higher, threshold) in zip(cols6, metrics_display):
                    s = score(key, val)
                    css_class = "metric-pass" if s is True else ("metric-fail" if s is False else "metric-na")
                    icon  = "PASS" if s is True else ("FAIL" if s is False else "—")
                    direction = f">= {threshold}" if higher else f"<= {threshold}"
                    val_str = f"{val:.2f}{unit}" if val is not None else "—"
                    col.markdown(f"""
                    <div class='metric-card {css_class}'>
                      <div class='mc-label'>{label}</div>
                      <div class='mc-value'>{val_str}</div>
                      <div class='mc-bench'>{icon} Ideal: {direction}{unit}</div>
                    </div>""", unsafe_allow_html=True)

                # ── ADVANCED METRICS (from yfinance) ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.expander("Metricas Avanzadas (yfinance)"):
                        with st.spinner("Consultando yfinance…"):
                            adv = valuation.compute_advanced_metrics(ticker_name)

                        ac1, ac2, ac3 = st.columns(3)

                        with ac1:
                            st.markdown("<div class='mc-label' style='margin-bottom:8px;'>DUPONT (ROE)</div>", unsafe_allow_html=True)
                            dp_items = [
                                ("Margen Neto", adv.get("dupont_net_margin"), "%"),
                                ("Rotacion Activos", adv.get("dupont_asset_turnover"), "x"),
                                ("Apalancamiento", adv.get("dupont_equity_multiplier"), "x"),
                                ("= ROE", adv.get("dupont_roe"), "%"),
                            ]
                            for lbl, v, u in dp_items:
                                v_str = f"{v:.2f}{u}" if v is not None else "—"
                                st.markdown(f"<div style='color:#94a3b8;font-size:12px;'>{lbl}: <span style='color:#f0f6ff;font-weight:600;'>{v_str}</span></div>", unsafe_allow_html=True)

                        with ac2:
                            st.markdown("<div class='mc-label' style='margin-bottom:8px;'>RETORNOS</div>", unsafe_allow_html=True)
                            ret_items = [
                                ("ROIC", adv.get("roic"), "%"),
                                ("ROCE", adv.get("roce"), "%"),
                                ("ROA", adv.get("roa"), "%"),
                                ("ROE", adv.get("roe"), "%"),
                            ]
                            for lbl, v, u in ret_items:
                                v_str = f"{v:.2f}{u}" if v is not None else "—"
                                clr = "#34d399" if v and v > 15 else ("#fbbf24" if v and v > 8 else "#f87171")
                                if v is None: clr = "#475569"
                                st.markdown(f"<div style='color:#94a3b8;font-size:12px;'>{lbl}: <span style='color:{clr};font-weight:600;'>{v_str}</span></div>", unsafe_allow_html=True)

                        with ac3:
                            st.markdown("<div class='mc-label' style='margin-bottom:8px;'>SOLVENCIA</div>", unsafe_allow_html=True)
                            sol_items = [
                                ("Deuda/EBITDA", adv.get("debt_ebitda"), "x"),
                                ("Cobertura Int.", adv.get("interest_coverage"), "x"),
                                ("Deuda/Equity", adv.get("debt_equity"), "x"),
                                ("Crec. Sostenible", adv.get("sustainable_growth"), "%"),
                            ]
                            for lbl, v, u in sol_items:
                                v_str = f"{v:.2f}{u}" if v is not None else "—"
                                st.markdown(f"<div style='color:#94a3b8;font-size:12px;'>{lbl}: <span style='color:#f0f6ff;font-weight:600;'>{v_str}</span></div>", unsafe_allow_html=True)

                # ── CHARTS ROW ──
                st.markdown("<div class='sec-title'>Analisis Visual</div>", unsafe_allow_html=True)
                ch1, ch2 = st.columns([1, 1])

                with ch1:
                    def norm(key, val):
                        if val is None: return 0
                        m2 = IDEAL.get(key, {})
                        if m2.get("higher", True):
                            th = m2.get("min", 1)
                            return min(val / th * 100, 150) if th else 0
                        else:
                            th = m2.get("max", 1)
                            return min((th / val) * 100, 150) if val > 0 else 0

                    r_keys = ["revenue_growth","profit_margin","roe","current_ratio","pe_ratio","debt_equity"]
                    r_vals = [norm(k, v) for k, (k2, v, *_) in zip(r_keys, metrics_display)]
                    r_labs = [IDEAL[k]["label"] for k in r_keys]
                    r_vals_c = r_vals + [r_vals[0]]
                    r_labs_c = r_labs + [r_labs[0]]

                    fig_r = go.Figure()
                    fig_r.add_trace(go.Scatterpolar(r=[100]*len(r_labs_c), theta=r_labs_c,
                        fill="toself", name="Ideal",
                        line=dict(color="#1e3a5f", width=1), fillcolor="rgba(30,58,95,0.3)"))
                    fig_r.add_trace(go.Scatterpolar(r=r_vals_c, theta=r_labs_c,
                        fill="toself", name=ticker_name,
                        line=dict(color="#60a5fa", width=2), fillcolor="rgba(96,165,250,0.15)"))
                    fig_r.update_layout(**DARK, height=320,
                        polar=dict(bgcolor="#0a0a0a",
                            angularaxis=dict(linecolor="#1a1a1a", gridcolor="#1a1a1a", color="#64748b"),
                            radialaxis=dict(linecolor="#1a1a1a", gridcolor="#1a1a1a",
                                          range=[0,150], showticklabels=False)),
                        legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"),
                        title=dict(text="Radar de Metricas", font=dict(color="#94a3b8", size=13), x=0.5))
                    st.plotly_chart(fig_r, use_container_width=True)

                with ch2:
                    bar_l, bar_v, bar_c = [], [], []
                    for lbl, v, color_hex in [
                        ("Ingresos",    m.get("revenue"),     "#60a5fa"),
                        ("Ben. Neto",   m.get("net_income"),  "#34d399"),
                        ("Deuda",       m.get("total_debt"),  "#f87171"),
                        ("Patrimonio",  m.get("total_equity"),"#a78bfa"),
                    ]:
                        if v and v > 0:
                            bar_l.append(lbl); bar_v.append(v); bar_c.append(color_hex)

                    if bar_l:
                        fig_b = go.Figure(go.Bar(
                            x=bar_l, y=bar_v, marker_color=bar_c,
                            text=[fmt(v) for v in bar_v], textposition="outside",
                            textfont=dict(color="#94a3b8", size=11),
                        ))
                        fig_b.update_layout(**DARK, height=320,
                            title=dict(text="Cifras Absolutas (USD)", font=dict(color="#94a3b8", size=13), x=0.5),
                            showlegend=False)
                        st.plotly_chart(fig_b, use_container_width=True)

                # ── VALUATION MULTIPLES (InvestingPro) ──
                val_multiples = parsed.get("valuation", {})
                if val_multiples:
                    with st.expander("Multiplos de Valoracion (Historico)"):
                        vm_df_data = {}
                        for metric_key, metric_vals in val_multiples.items():
                            label = metric_key.replace("_", " ").title()
                            vm_df_data[label] = metric_vals
                        if vm_df_data:
                            vm_df = pd.DataFrame(vm_df_data).T
                            st.dataframe(vm_df, use_container_width=True)

                # ── FINANCIAL STATEMENTS (InvestingPro) ──
                fin_annual = parsed.get("financials_annual", {})
                if fin_annual.get("income") or fin_annual.get("balance"):
                    with st.expander("Estados Financieros (Anuales)"):
                        for stmt_name, stmt_label in [("income","Estado de Resultados"),
                                                       ("balance","Balance General"),
                                                       ("cashflow","Flujo de Caja")]:
                            data = fin_annual.get(stmt_name, {})
                            if data:
                                st.markdown(f"**{stmt_label}** *(USD millones)*")
                                df_stmt = pd.DataFrame(data).T
                                df_stmt.index = [k.replace("_"," ").title() for k in df_stmt.index]
                                st.dataframe(df_stmt.style.format("{:,.0f}", na_rep="—"), use_container_width=True)

                # ── ANALYST RATINGS (InvestingPro) ──
                analyst_data = parsed.get("analyst", {})
                if analyst_data.get("ratings"):
                    with st.expander(f"Ratings de Analistas ({len(analyst_data['ratings'])})"):
                        if analyst_data.get("eps_forecasts"):
                            st.markdown("**Proyecciones EPS**")
                            eps_df = pd.DataFrame(analyst_data["eps_forecasts"])
                            st.dataframe(eps_df, use_container_width=True, hide_index=True)
                        st.markdown("**Ultimas Calificaciones**")
                        rt_df = pd.DataFrame(analyst_data["ratings"])
                        st.dataframe(rt_df, use_container_width=True, hide_index=True)

                # ── SWOT (InvestingPro) ──
                swot = parsed.get("swot", {})
                if any(swot.get(k) for k in ("strengths","weaknesses","opportunities","threats")):
                    with st.expander("Analisis SWOT"):
                        sw1, sw2 = st.columns(2)
                        with sw1:
                            st.markdown("**Fortalezas**")
                            for s_item in swot.get("strengths", []):
                                st.markdown(f"- {s_item}")
                            st.markdown("**Oportunidades**")
                            for s_item in swot.get("opportunities", []):
                                st.markdown(f"- {s_item}")
                        with sw2:
                            st.markdown("**Debilidades**")
                            for s_item in swot.get("weaknesses", []):
                                st.markdown(f"- {s_item}")
                            st.markdown("**Amenazas**")
                            for s_item in swot.get("threats", []):
                                st.markdown(f"- {s_item}")

                # ── PRO TIPS ──
                pro_tips = parsed.get("pro_tips", [])
                if pro_tips:
                    with st.expander(f"Pro Tips ({len(pro_tips)})"):
                        for tip in pro_tips:
                            st.markdown(f"- {tip}")

                # ── EXECUTIVE SUMMARY ──
                exec_summary = parsed.get("executive_summary", "")
                if exec_summary:
                    with st.expander("Resumen Ejecutivo"):
                        st.write(exec_summary)

                # ── GAUGE CHARTS ──
                gauge_metrics = [
                    ("Margen Neto",     m.get("profit_margin"), 0, 40, 15, "%"),
                    ("ROE",             m.get("roe"),           0, 40, 15, "%"),
                    ("P/E Ratio",       m.get("pe_ratio"),      0, 50, 25, "x"),
                ]
                g_cols = st.columns(3)
                for col, (lbl, val, vmin, vmax, threshold, unit) in zip(g_cols, gauge_metrics):
                    if val is not None:
                        gcolor = "#34d399" if score(lbl.lower().replace(" ","_").replace("/","_").replace(".",""), val) else "#f87171"
                        fig_g = go.Figure(go.Indicator(
                            mode="gauge+number",
                            value=val,
                            number=dict(suffix=unit, font=dict(color="#f0f6ff", size=24)),
                            title=dict(text=lbl, font=dict(color="#94a3b8", size=13)),
                            gauge=dict(
                                axis=dict(range=[vmin, vmax], tickcolor="#475569",
                                         tickfont=dict(color="#475569", size=10)),
                                bar=dict(color=gcolor, thickness=0.6),
                                bgcolor="#0a0a0a",
                                bordercolor="#1a1a1a",
                                steps=[dict(range=[vmin, vmax], color="#0d1829")],
                                threshold=dict(
                                    line=dict(color="#fbbf24", width=2),
                                    thickness=0.75,
                                    value=threshold
                                ),
                            )
                        ))
                        fig_g.update_layout(**dark_layout(height=200, margin=dict(l=24,r=24,t=40,b=10)))
                        col.plotly_chart(fig_g, use_container_width=True)

                # ── BUFFETT/DORSEY CHECKLIST ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.expander("🏆 Checklist Buffett/Dorsey — Quality Score"):
                        try:
                            _render_quality_score(ticker_name)
                        except Exception as e:
                            st.warning(f"Error calculando quality score: {e}")

                # ── DCF SCENARIOS ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.expander("🎯 DCF — 3 Escenarios (Pesimista / Base / Optimista)"):
                        try:
                            _render_dcf_scenarios(ticker_name, parsed)
                        except Exception as e:
                            st.warning(f"Error calculando escenarios DCF: {e}")

                # ── INSIDER TRADING ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.expander("🕵️ Insider Trading — Transacciones de Insiders"):
                        try:
                            _render_insider_trading(ticker_name)
                        except Exception as e:
                            st.warning(f"Error obteniendo insider trading: {e}")

                # ── AI ANALYSIS (PDF) ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    providers = ai_engine.get_available_providers()
                    if providers:
                        st.markdown("<div class='sec-title'>Análisis con IA</div>", unsafe_allow_html=True)
                        st.caption(f"🤖 Proveedores: {', '.join(providers)}")
                        if st.button("🧠 Generar Análisis IA", key="ai_pdf"):
                            with st.spinner("Generando análisis con IA…"):
                                ai_result = ai_engine.analyze_stock(
                                    ticker_name,
                                    price=fv.get("current_price") if fv else None,
                                    pe=m.get("pe_ratio"),
                                    roe=m.get("roe"),
                                    margin=m.get("profit_margin"),
                                    revenue_growth=m.get("revenue_growth"),
                                    debt_equity=debt_eq,
                                    fair_value=fv.get("avg_fair_value") if fv else None,
                                )
                                if ai_result:
                                    st.markdown(f"""<div style='background:rgba(96,165,250,0.06);border:1px solid rgba(96,165,250,0.2);
                                                border-radius:14px;padding:20px;color:#c8d6e5;font-size:13px;line-height:1.7;'>
                                      {ai_result}
                                    </div>""", unsafe_allow_html=True)
                                else:
                                    st.warning("No se pudo generar el análisis con IA.")

                # ── AUTO-SAVE + REPORT ──
                st.markdown("---")
                # Auto-save on first analysis
                save_key = f"saved_{uploaded.name}_{ticker_name}"
                if save_key not in st.session_state:
                    m["ticker"] = ticker_name
                    db.save_stock_analysis(m, uploaded.name)
                    st.session_state[save_key] = True
                    st.success("Analisis guardado automaticamente.")

                sc1, sc2, sc3 = st.columns([2, 1, 1])
                with sc2:
                    if st.button("Guardar copia adicional"):
                        m["ticker"] = ticker_name
                        db.save_stock_analysis(m, uploaded.name)
                        st.success("Copia guardada.")
                with sc3:
                    thesis_data = db.get_investment_notes(ticker_name)
                    try:
                        pdf_bytes = report_generator.generate_report(
                            ticker_name,
                            parsed_data=parsed,
                            fair_value=fv,
                            advanced=adv,
                            thesis=thesis_data if thesis_data else None,
                        )
                        import file_saver
                        file_saver.save_or_download(
                            pdf_bytes,
                            f"{ticker_name}_informe_{datetime.now().strftime('%Y%m%d')}.pdf",
                            "application/pdf",
                            "📥 Descargar Informe PDF",
                            key="exp_pdf_report",
                        )
                    except Exception as e:
                        st.warning(f"Error generando informe: {e}")

            except Exception as e:
                st.error(f"Error procesando PDF: {e}")
                import traceback
                st.code(traceback.format_exc())

    # ══════════════════════════════════════════════════════════════
    # STANDALONE TICKER ANALYSIS (without PDF)
    # ══════════════════════════════════════════════════════════════
    if not uploaded and manual_ticker and manual_ticker.strip():
        ticker_solo = manual_ticker.strip().upper()
        # Sync to global state
        st.session_state.active_ticker = ticker_solo

        st.markdown(f"""
        <div style='background:#000000;border:1px solid #1a1a1a;
                    border-radius:14px;padding:24px 28px;margin-bottom:20px;'>
          <div style='font-size:28px;font-weight:700;color:#f0f6ff;'>{ticker_solo}</div>
          <div style='font-size:13px;color:#64748b;margin-top:4px;'>Análisis rápido por ticker · Sin PDF</div>
        </div>""", unsafe_allow_html=True)

        # ── Master Chart (TradingView Advanced) ──
        try:
            _tradingview_chart(ticker_solo)
        except Exception:
            st.info("No se pudo cargar el chart de TradingView.")

        # ── Analyst Insights (Symbol Info + TA Gauge) ──
        try:
            _tradingview_analyst_insights(ticker_solo)
        except Exception:
            pass

        # ── Institutional News (Timeline) ──
        with st.expander("📰 Noticias Institucionales", expanded=False):
            try:
                _tradingview_news(ticker_solo)
            except Exception:
                st.info("No se pudieron cargar noticias.")

        # ── Fair Value ──
        with st.spinner("Calculando Fair Value…"):
            fv_solo = valuation.compute_fair_values(ticker_solo, {})
        if fv_solo and fv_solo.get("avg_fair_value"):
            st.markdown("<div class='sec-title'>Fair Value & Semáforo</div>", unsafe_allow_html=True)
            fv_cols = st.columns(4)
            sig_colors = {"green": "#34d399", "yellow": "#fbbf24", "red": "#f87171"}
            sig_labels = {"undervalued": "INFRAVALORADA", "fair": "VALOR JUSTO", "overvalued": "SOBREVALORADA"}
            sig_bg = {"green": "#064e3b", "yellow": "#422006", "red": "#451a03"}
            sc_fv = fv_solo.get("signal_color") or "yellow"
            fv_cols[0].markdown(kpi("Precio Actual", f"${fv_solo['current_price']:,.2f}", "", "blue"), unsafe_allow_html=True)
            if fv_solo.get("pe_fair_value"):
                fv_cols[1].markdown(kpi("FV Múltiplos", f"${fv_solo['pe_fair_value']:,.2f}", "", "purple"), unsafe_allow_html=True)
            if fv_solo.get("dcf_fair_value"):
                fv_cols[2].markdown(kpi("FV DCF", f"${fv_solo['dcf_fair_value']:,.2f}", "", "purple"), unsafe_allow_html=True)
            fv_cols[3].markdown(f"""
            <div style='background:{sig_bg[sc_fv]};border:2px solid {sig_colors[sc_fv]};border-radius:14px;
                        padding:16px;text-align:center;'>
              <div style='font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;'>Señal</div>
              <div style='font-size:22px;font-weight:800;color:{sig_colors[sc_fv]};'>{sig_labels.get(fv_solo['signal'],'')}</div>
              <div style='font-size:13px;color:#64748b;'>FV Prom: ${fv_solo["avg_fair_value"]:,.2f} ({fv_solo["upside_pct"]:+.1f}%)</div>
            </div>""", unsafe_allow_html=True)

        # ── Card Margen de Seguridad ──
        if fv_solo and fv_solo.get("avg_fair_value") and fv_solo.get("current_price"):
            _margin_of_safety_card(fv_solo["current_price"], fv_solo["avg_fair_value"], ticker_solo)

        # ── Snowflake Radar ──
        with st.expander("❄️ Snowflake — Análisis 5 Dimensiones", expanded=True):
            try:
                _snowflake_radar(ticker_solo)
            except Exception as e:
                st.warning(f"Error: {e}")

        # ── Analyst Price Targets ──
        with st.expander("🎯 Price Targets de Analistas"):
            try:
                _analyst_price_targets(ticker_solo)
            except Exception as e:
                st.warning(f"Error: {e}")

        # ── Peer Comparison ──
        with st.expander("📊 Comparación con Peers"):
            try:
                _peer_comparison(ticker_solo)
            except Exception as e:
                st.warning(f"Error: {e}")

        # ── Financial Health Score (Altman Z + Piotroski F) ──
        with st.expander("🏥 Salud Financiera (Altman Z + Piotroski F)"):
            try:
                hs = valuation.compute_health_scores(ticker_solo)
                if hs.get("z_score") is not None or hs.get("f_score") is not None:
                    hc1, hc2 = st.columns(2)
                    with hc1:
                        if hs.get("z_score") is not None:
                            z_color = {"SAFE": "#34d399", "GREY": "#fbbf24", "DISTRESS": "#f87171"}.get(hs["z_label"], "#94a3b8")
                            z_label_es = {"SAFE": "SEGURO", "GREY": "ZONA GRIS", "DISTRESS": "RIESGO"}.get(hs["z_label"], "N/A")
                            st.markdown(f"""
                            <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:14px;padding:20px;text-align:center;'>
                              <div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1px;'>Altman Z-Score</div>
                              <div style='font-size:32px;font-weight:800;color:{z_color};margin:8px 0;'>{hs['z_score']}</div>
                              <div style='font-size:14px;font-weight:600;color:{z_color};'>{z_label_es}</div>
                              <div style='font-size:11px;color:#475569;margin-top:4px;'>{"Z > 2.99 = seguro" if hs["z_score"] > 2.99 else ("1.81 < Z < 2.99 = zona gris" if hs["z_score"] > 1.81 else "Z < 1.81 = riesgo quiebra")}</div>
                            </div>""", unsafe_allow_html=True)
                    with hc2:
                        if hs.get("f_score") is not None:
                            f_color = {"STRONG": "#34d399", "MODERATE": "#fbbf24", "WEAK": "#f87171"}.get(hs["f_label"], "#94a3b8")
                            f_label_es = {"STRONG": "FUERTE", "MODERATE": "MODERADO", "WEAK": "DÉBIL"}.get(hs["f_label"], "N/A")
                            st.markdown(f"""
                            <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:14px;padding:20px;text-align:center;'>
                              <div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1px;'>Piotroski F-Score</div>
                              <div style='font-size:32px;font-weight:800;color:{f_color};margin:8px 0;'>{hs['f_score']}/9</div>
                              <div style='font-size:14px;font-weight:600;color:{f_color};'>{f_label_es}</div>
                              <div style='font-size:11px;color:#475569;margin-top:4px;'>{"F ≥ 7 = fuerte" if hs["f_score"] >= 7 else ("4 ≤ F < 7 = moderado" if hs["f_score"] >= 4 else "F < 4 = débil")}</div>
                            </div>""", unsafe_allow_html=True)
                        # Show Piotroski details
                        if hs.get("f_details"):
                            for criterion, passed in hs["f_details"].items():
                                icon = "✅" if passed else "❌"
                                st.markdown(f"<span style='color:{('#34d399' if passed else '#f87171')};font-size:12px;'>{icon} {criterion}</span>", unsafe_allow_html=True)
                else:
                    st.info("No se pudieron calcular los scores de salud financiera.")
            except Exception as e:
                st.warning(f"Error: {e}")

        # ── Buffett/Dorsey Checklist ──
        st.markdown("<div class='sec-title'>Checklist Buffett/Dorsey</div>", unsafe_allow_html=True)
        try:
            _render_quality_score(ticker_solo)
        except Exception as e:
            st.warning(f"Error calculando quality score: {e}")

        # ── DCF Scenarios ──
        st.markdown("<div class='sec-title'>DCF — 3 Escenarios</div>", unsafe_allow_html=True)
        try:
            _render_dcf_scenarios(ticker_solo)
        except Exception as e:
            st.warning(f"Error calculando escenarios DCF: {e}")

        # ── Insider Trading ──
        st.markdown("<div class='sec-title'>Insider Trading</div>", unsafe_allow_html=True)
        try:
            _render_insider_trading(ticker_solo)
        except Exception as e:
            st.warning(f"Error obteniendo insider trading: {e}")

        # ── AI ANALYSIS (standalone) ──
        st.markdown("<div class='sec-title'>Análisis con IA</div>", unsafe_allow_html=True)
        providers = ai_engine.get_available_providers()
        if providers:
            st.caption(f"🤖 Proveedores disponibles: {', '.join(providers)}")
            if st.button("🧠 Generar Análisis IA", key="ai_standalone"):
                with st.spinner("Generando análisis con IA…"):
                    ai_price = None
                    ai_fv = None
                    try:
                        if fv_solo and fv_solo.get("current_price"):
                            ai_price = fv_solo["current_price"]
                            ai_fv = fv_solo.get("avg_fair_value")
                    except Exception:
                        pass
                    ai_result = ai_engine.analyze_stock(
                        ticker_solo, price=ai_price, fair_value=ai_fv,
                    )
                    if ai_result:
                        st.markdown(f"""<div style='background:rgba(96,165,250,0.06);border:1px solid rgba(96,165,250,0.2);
                                    border-radius:14px;padding:20px;color:#c8d6e5;font-size:13px;line-height:1.7;'>
                          {ai_result}
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.warning("No se pudo generar análisis. Verifica API keys en secrets.toml")
        else:
            st.info("Configura API keys (Gemini/Groq/OpenRouter) en secrets.toml para análisis con IA.")

    # ── EXCEL EXPORT (analyses) ──
    analyses_data = db.get_stock_analyses()
    if not analyses_data.empty:
        xlsx2 = excel_export.export_analyses(analyses_data)
        import file_saver
        file_saver.save_or_download(xlsx2, "analisis_quantum.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          "📥 Exportar Análisis (Excel)", key="exp_analisis_sa")

    # ── SAVED ANALYSES TABLE ──
    st.markdown("<div class='sec-title'>Historial de Analisis</div>", unsafe_allow_html=True)
    df_new = db.get_stock_analyses()
    df_old = db.get_analyses()
    if df_new.empty and df_old.empty:
        st.info("Aun no hay analisis guardados. Sube un PDF y guardalo.")
    else:
        if not df_new.empty:
            cols_show = ["ticker","company_name","price","pe_ratio","pe_fwd","peg_ratio","profit_margin","revenue_growth","roe","ev_ebitda","analyzed_at"]
            available = [c for c in cols_show if c in df_new.columns]
            df_show = df_new[available].copy()
            col_names = {"ticker":"Ticker","company_name":"Empresa","price":"Precio","pe_ratio":"P/E",
                        "pe_fwd":"P/E Fwd","peg_ratio":"PEG","profit_margin":"Margen %",
                        "revenue_growth":"Crec %","roe":"ROE %","ev_ebitda":"EV/EBITDA","analyzed_at":"Fecha"}
            df_show.rename(columns={c: col_names.get(c,c) for c in available}, inplace=True)
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        if not df_old.empty:
            with st.expander("Analisis anteriores (formato legacy)"):
                cols_show = ["ticker","filename","profit_margin","revenue_growth","roe","pe_ratio","current_ratio","analyzed_at"]
                df_show2 = df_old[[c for c in cols_show if c in df_old.columns]].copy()
                df_show2.columns = ["Ticker","Archivo","Margen %","Crec. %","ROE %","P/E","Ratio Corr.","Fecha"][:len(df_show2.columns)]
                st.dataframe(df_show2, use_container_width=True, hide_index=True)

    # ── EVOLUTION COMPARISON ──
    analyzed_tickers = db.get_analyzed_tickers()
    if analyzed_tickers:
        st.markdown("<div class='sec-title'>Evolucion Comparativa</div>", unsafe_allow_html=True)
        sel_ticker = st.selectbox("Selecciona ticker para comparar evolución", [""] + analyzed_tickers)
        if sel_ticker:
            hist_df = db.get_ticker_history(sel_ticker)
            if len(hist_df) >= 2:
                st.markdown(f"**{sel_ticker}** — {len(hist_df)} análisis guardados", unsafe_allow_html=True)

                # Comparison table
                evo_cols = ["analyzed_at","price","pe_ratio","pe_fwd","profit_margin","revenue_growth","roe","ev_ebitda","debt_equity"]
                evo_available = [c for c in evo_cols if c in hist_df.columns]
                evo_df = hist_df[evo_available].copy()
                evo_labels = {"analyzed_at":"Fecha","price":"Precio","pe_ratio":"P/E","pe_fwd":"P/E Fwd",
                              "profit_margin":"Margen %","revenue_growth":"Crec %","roe":"ROE %",
                              "ev_ebitda":"EV/EBITDA","debt_equity":"D/E"}
                evo_df.rename(columns={c: evo_labels.get(c,c) for c in evo_available}, inplace=True)
                st.dataframe(evo_df, use_container_width=True, hide_index=True)

                # Delta badges between last two
                latest = hist_df.iloc[-1]
                prev = hist_df.iloc[-2]
                delta_cols = st.columns(6)
                delta_metrics = [
                    ("Precio", "price", "$", True),
                    ("P/E", "pe_ratio", "x", False),
                    ("Margen %", "profit_margin", "%", True),
                    ("Crec %", "revenue_growth", "%", True),
                    ("ROE %", "roe", "%", True),
                    ("D/E", "debt_equity", "x", False),
                ]
                for col, (label, key, unit, higher_better) in zip(delta_cols, delta_metrics):
                    v_new = latest.get(key)
                    v_old = prev.get(key)
                    if v_new is not None and v_old is not None and not (isinstance(v_new, float) and pd.isna(v_new)) and not (isinstance(v_old, float) and pd.isna(v_old)):
                        delta = v_new - v_old
                        is_good = (delta > 0) == higher_better
                        d_color = "#34d399" if is_good else "#f87171"
                        d_sign = "+" if delta > 0 else ""
                        prefix = "$" if unit == "$" else ""
                        col.markdown(f"""
                        <div class='metric-card {"metric-pass" if is_good else "metric-fail"}'>
                          <div class='mc-label'>{label}</div>
                          <div class='mc-value'>{prefix}{v_new:.2f}{unit if unit != "$" else ""}</div>
                          <div style='font-size:12px;color:{d_color};font-weight:600;'>{d_sign}{delta:.2f} vs anterior</div>
                        </div>""", unsafe_allow_html=True)

                # Evolution charts
                if len(hist_df) >= 2:
                    ech1, ech2 = st.columns(2)
                    with ech1:
                        fig_evo = go.Figure()
                        for metric_key, metric_label, color in [
                            ("profit_margin", "Margen Neto %", "#60a5fa"),
                            ("roe", "ROE %", "#34d399"),
                            ("revenue_growth", "Crec. Ingresos %", "#fbbf24"),
                        ]:
                            vals = hist_df[metric_key].dropna()
                            if not vals.empty:
                                fig_evo.add_trace(go.Scatter(
                                    x=hist_df.loc[vals.index, "analyzed_at"],
                                    y=vals, name=metric_label,
                                    mode="lines+markers",
                                    line=dict(color=color, width=2),
                                    marker=dict(size=8),
                                ))
                        fig_evo.update_layout(**DARK, height=300,
                            title=dict(text="Evolución de Ratios", font=dict(color="#94a3b8", size=13), x=0.5),
                            legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"))
                        st.plotly_chart(fig_evo, use_container_width=True)

                    with ech2:
                        fig_price = go.Figure()
                        price_vals = hist_df["price"].dropna()
                        if not price_vals.empty:
                            fig_price.add_trace(go.Scatter(
                                x=hist_df.loc[price_vals.index, "analyzed_at"],
                                y=price_vals, name="Precio",
                                mode="lines+markers",
                                line=dict(color="#a78bfa", width=2.5),
                                marker=dict(size=8),
                                fill="tozeroy", fillcolor="rgba(167,139,250,0.08)",
                            ))
                        pe_vals = hist_df["pe_ratio"].dropna()
                        if not pe_vals.empty:
                            fig_price.add_trace(go.Scatter(
                                x=hist_df.loc[pe_vals.index, "analyzed_at"],
                                y=pe_vals, name="P/E",
                                mode="lines+markers", yaxis="y2",
                                line=dict(color="#f87171", width=2, dash="dot"),
                                marker=dict(size=6),
                            ))
                        fig_price.update_layout(**dark_layout(height=300,
                            title=dict(text="Precio vs P/E", font=dict(color="#94a3b8", size=13), x=0.5),
                            yaxis=dict(title="Precio ($)"),
                            yaxis2=dict(title="P/E", overlaying="y", side="right", showgrid=False),
                            legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a")))
                        st.plotly_chart(fig_price, use_container_width=True)
            elif len(hist_df) == 1:
                st.info(f"Solo hay 1 análisis para {sel_ticker}. Sube otro reporte para ver la evolución.")
