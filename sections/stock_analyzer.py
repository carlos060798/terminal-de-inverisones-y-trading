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
import ml_engine
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

        # ── G2: 52-Week Range Bar ──
        try:
            _tk_g2 = yf.Ticker(ticker_solo)
            _info_g2 = _tk_g2.info
            _price_g2 = _info_g2.get("currentPrice") or _info_g2.get("regularMarketPrice") or 0
            _low52_g2 = _info_g2.get("fiftyTwoWeekLow") or 0
            _high52_g2 = _info_g2.get("fiftyTwoWeekHigh") or 0
            if _price_g2 > 0 and _high52_g2 > _low52_g2:
                _pct_g2 = ((_price_g2 - _low52_g2) / (_high52_g2 - _low52_g2)) * 100
                _pct_g2 = max(0, min(100, _pct_g2))
                _bar_color_g2 = "#34d399" if _pct_g2 > 60 else ("#fbbf24" if _pct_g2 > 30 else "#f87171")
                st.markdown(f"""
                <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:12px;padding:16px 20px;margin-bottom:16px;'>
                  <div style='display:flex;justify-content:space-between;margin-bottom:8px;'>
                    <span style='color:#5a6f8a;font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:600;'>52-Week Range</span>
                    <span style='color:#f0f6ff;font-size:13px;font-weight:600;'>${_price_g2:,.2f} ({_pct_g2:.0f}%)</span>
                  </div>
                  <div style='display:flex;align-items:center;gap:10px;'>
                    <span style='color:#f87171;font-size:12px;font-weight:600;'>${_low52_g2:,.2f}</span>
                    <div style='flex:1;background:#1a1a1a;border-radius:6px;height:12px;overflow:hidden;position:relative;'>
                      <div style='background:linear-gradient(90deg, #f87171, #fbbf24, #34d399);width:100%;height:100%;opacity:0.2;'></div>
                      <div style='position:absolute;top:0;left:0;background:{_bar_color_g2};width:{_pct_g2}%;height:100%;border-radius:6px;
                                  transition:width 0.5s ease;'></div>
                      <div style='position:absolute;top:-2px;left:{_pct_g2}%;width:4px;height:16px;background:#f0f6ff;border-radius:2px;
                                  margin-left:-2px;'></div>
                    </div>
                    <span style='color:#34d399;font-size:12px;font-weight:600;'>${_high52_g2:,.2f}</span>
                  </div>
                </div>""", unsafe_allow_html=True)
        except Exception:
            pass

        # ── G4: Short Interest ──
        try:
            _info_g4 = yf.Ticker(ticker_solo).info
            _short_pct = _info_g4.get("shortPercentOfFloat")
            _short_ratio = _info_g4.get("shortRatio")
            if _short_pct is not None:
                _short_pct_val = _short_pct * 100 if _short_pct < 1 else _short_pct
                _short_color = "red" if _short_pct_val > 20 else ("yellow" if _short_pct_val > 10 else "green")
                _short_sub = f"Short Ratio: {_short_ratio:.1f} days" if _short_ratio else ""
                st.markdown(kpi("Short Interest", f"{_short_pct_val:.1f}%", _short_sub, _short_color), unsafe_allow_html=True)
        except Exception:
            pass

        # ── G8: Price vs Moving Averages Signal ──
        with st.expander("📊 Señales Medias Móviles", expanded=False):
            try:
                _hist_g8 = yf.Ticker(ticker_solo).history(period="1y")
                if _hist_g8 is not None and len(_hist_g8) > 0:
                    _price_g8 = _hist_g8["Close"].iloc[-1]
                    _ma20_g8 = _hist_g8["Close"].rolling(20).mean().iloc[-1] if len(_hist_g8) >= 20 else None
                    _ma50_g8 = _hist_g8["Close"].rolling(50).mean().iloc[-1] if len(_hist_g8) >= 50 else None
                    _ma200_g8 = _hist_g8["Close"].rolling(200).mean().iloc[-1] if len(_hist_g8) >= 200 else None

                    _ma_rows = []
                    _bullish_count = 0
                    _total_count = 0
                    for _ma_label, _ma_val in [("MA 20", _ma20_g8), ("MA 50", _ma50_g8), ("MA 200", _ma200_g8)]:
                        if _ma_val is not None:
                            _total_count += 1
                            _above = _price_g8 >= _ma_val
                            if _above:
                                _bullish_count += 1
                            _icon = "✅" if _above else "❌"
                            _signal_txt = "ALCISTA" if _above else "BAJISTA"
                            _clr = "#34d399" if _above else "#f87171"
                            _diff_pct = ((_price_g8 - _ma_val) / _ma_val) * 100
                            _ma_rows.append(f"""
                            <tr>
                              <td style='padding:8px 12px;color:#f0f6ff;font-weight:600;'>{_ma_label}</td>
                              <td style='padding:8px 12px;color:#94a3b8;'>${_ma_val:,.2f}</td>
                              <td style='padding:8px 12px;color:{_clr};font-weight:600;'>{_diff_pct:+.2f}%</td>
                              <td style='padding:8px 12px;'>{_icon} <span style='color:{_clr};font-weight:600;'>{_signal_txt}</span></td>
                            </tr>""")

                    if _ma_rows:
                        # Summary badge
                        if _total_count > 0:
                            if _bullish_count == _total_count:
                                _summary_lbl = f"{_bullish_count}/{_total_count} BULLISH"
                                _summary_clr = "#34d399"
                                _summary_bg = "#064e3b"
                            elif _bullish_count == 0:
                                _summary_lbl = f"0/{_total_count} BEARISH"
                                _summary_clr = "#f87171"
                                _summary_bg = "#451a03"
                            else:
                                _summary_lbl = f"{_bullish_count}/{_total_count} MIXTO"
                                _summary_clr = "#fbbf24"
                                _summary_bg = "#422006"

                            st.markdown(f"""
                            <div style='text-align:center;margin-bottom:12px;'>
                              <span style='background:{_summary_bg};border:1px solid {_summary_clr};
                                          border-radius:8px;padding:6px 16px;color:{_summary_clr};
                                          font-weight:700;font-size:14px;'>{_summary_lbl}</span>
                              <span style='color:#5a6f8a;font-size:12px;margin-left:12px;'>
                                Precio actual: ${_price_g8:,.2f}</span>
                            </div>""", unsafe_allow_html=True)

                        _table_html = """
                        <table style='width:100%;border-collapse:collapse;background:#0a0a0a;border:1px solid #1a1a1a;border-radius:10px;'>
                          <thead>
                            <tr style='border-bottom:1px solid #1a1a1a;'>
                              <th style='padding:8px 12px;text-align:left;color:#5a6f8a;font-size:11px;text-transform:uppercase;letter-spacing:1px;'>Media Móvil</th>
                              <th style='padding:8px 12px;text-align:left;color:#5a6f8a;font-size:11px;text-transform:uppercase;letter-spacing:1px;'>Valor</th>
                              <th style='padding:8px 12px;text-align:left;color:#5a6f8a;font-size:11px;text-transform:uppercase;letter-spacing:1px;'>Precio vs MA</th>
                              <th style='padding:8px 12px;text-align:left;color:#5a6f8a;font-size:11px;text-transform:uppercase;letter-spacing:1px;'>Señal</th>
                            </tr>
                          </thead>
                          <tbody>""" + "".join(_ma_rows) + """
                          </tbody>
                        </table>"""
                        st.markdown(_table_html, unsafe_allow_html=True)
                    else:
                        st.info("No hay suficientes datos para calcular medias móviles.")
                else:
                    st.info("No se pudieron obtener datos históricos.")
            except Exception as _e_g8:
                st.warning(f"Error calculando señales de medias móviles: {_e_g8}")

        # ── G10: Relative Strength vs S&P 500 ──
        try:
            _hist_g10 = yf.download(ticker_solo, period="3mo", progress=False)
            _spy_g10 = yf.download("SPY", period="3mo", progress=False)
            if _hist_g10 is not None and not _hist_g10.empty and _spy_g10 is not None and not _spy_g10.empty:
                if isinstance(_hist_g10.columns, pd.MultiIndex):
                    _tk_close_g10 = _hist_g10["Close"].iloc[:, 0]
                else:
                    _tk_close_g10 = _hist_g10["Close"]
                if isinstance(_spy_g10.columns, pd.MultiIndex):
                    _spy_close_g10 = _spy_g10["Close"].iloc[:, 0]
                else:
                    _spy_close_g10 = _spy_g10["Close"]
                _tk_ret_g10 = (_tk_close_g10.iloc[-1] / _tk_close_g10.iloc[0] - 1) * 100
                _spy_ret_g10 = (_spy_close_g10.iloc[-1] / _spy_close_g10.iloc[0] - 1) * 100
                # Ratio: RS = ticker_return / spy_return (handle zero)
                if abs(_spy_ret_g10) > 0.001:
                    _rs_ratio = (1 + _tk_ret_g10 / 100) / (1 + _spy_ret_g10 / 100)
                else:
                    _rs_ratio = 1.0
                _rs_label = "Outperforming" if _rs_ratio > 1 else "Underperforming"
                _rs_color = "green" if _rs_ratio > 1 else "red"
                st.markdown(kpi("RS vs S&P", f"{_rs_ratio:.2f}x ({_rs_label})",
                               f"{ticker_solo}: {_tk_ret_g10:+.1f}% | SPY: {_spy_ret_g10:+.1f}% (3M)", _rs_color),
                           unsafe_allow_html=True)
        except Exception:
            pass

        # ── G3: Earnings Surprise ──
        with st.expander("📊 Earnings Surprise (Ultimos 4 Trimestres)", expanded=False):
            try:
                _tk_g3 = yf.Ticker(ticker_solo)
                _eh_g3 = getattr(_tk_g3, 'earnings_history', None)
                if _eh_g3 is None:
                    _eh_g3 = getattr(_tk_g3, 'quarterly_earnings', None)
                if _eh_g3 is not None and not _eh_g3.empty:
                    _eh_display = _eh_g3.head(4).copy()
                    st.dataframe(_eh_display, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay datos de earnings surprise disponibles.")
            except Exception as _e_g3:
                st.info(f"No se pudieron cargar earnings surprise: {_e_g3}")

        # ── G7: Dividend Safety Score (Enhanced) ──
        with st.expander("🛡 Dividend Safety Score", expanded=False):
            try:
                _tk_g7 = yf.Ticker(ticker_solo)
                _info_g7 = _tk_g7.info
                _div_yield_g7 = (_info_g7.get("dividendYield") or 0) * 100
                _payout_g7 = _info_g7.get("payoutRatio") or 0
                _payout_pct = _payout_g7 * 100 if _payout_g7 < 2 else _payout_g7
                _fcf_ps = _info_g7.get("freeCashflow") or 0
                _div_rate = _info_g7.get("dividendRate") or 0
                _shares_out = _info_g7.get("sharesOutstanding") or 1
                _total_div = _div_rate * _shares_out
                _fcf_payout = (_total_div / _fcf_ps * 100) if _fcf_ps > 0 else 999
                _debt_equity = _info_g7.get("debtToEquity") or 0
                _debt_equity_ratio = _debt_equity / 100 if _debt_equity > 5 else _debt_equity

                # Consecutive years of dividends
                try:
                    _divs_g7 = _tk_g7.dividends
                    if _divs_g7 is not None and len(_divs_g7) > 0:
                        _div_years = len(_divs_g7.resample('YE').sum().loc[lambda x: x > 0])
                    else:
                        _div_years = 0
                except Exception:
                    _div_years = 0

                # Score (0-100) based on 4 criteria
                _div_score = 0
                _breakdown = []

                # 1) Payout Ratio (max 30pts)
                if _payout_pct > 0 and _payout_pct < 60:
                    _pr_pts = 30
                elif _payout_pct > 0 and _payout_pct < 80:
                    _pr_pts = 20
                else:
                    _pr_pts = 0
                _div_score += _pr_pts
                _breakdown.append(("Payout Ratio", f"{_payout_pct:.1f}%", "< 60%", f"{_pr_pts}/30"))

                # 2) FCF Payout (max 25pts)
                if _fcf_payout < 70:
                    _fcf_pts = 25
                elif _fcf_payout < 90:
                    _fcf_pts = 15
                else:
                    _fcf_pts = 0
                _div_score += _fcf_pts
                _breakdown.append(("FCF Payout", f"{_fcf_payout:.1f}%", "< 70%", f"{_fcf_pts}/25"))

                # 3) Consecutive years of dividends (max 25pts)
                if _div_years > 10:
                    _yr_pts = 25
                elif _div_years > 5:
                    _yr_pts = 15
                else:
                    _yr_pts = 5
                _div_score += _yr_pts
                _breakdown.append(("Anos Dividendos", f"{_div_years}y", "> 10y", f"{_yr_pts}/25"))

                # 4) Debt/Equity (max 20pts)
                if _debt_equity_ratio < 1:
                    _de_pts = 20
                elif _debt_equity_ratio < 2:
                    _de_pts = 10
                else:
                    _de_pts = 0
                _div_score += _de_pts
                _breakdown.append(("Debt/Equity", f"{_debt_equity_ratio:.2f}", "< 1.0", f"{_de_pts}/20"))

                if _div_yield_g7 > 0:
                    _ds_color = "#34d399" if _div_score >= 70 else ("#fbbf24" if _div_score >= 40 else "#f87171")
                    _ds_label = "SEGURO" if _div_score >= 70 else ("MODERADO" if _div_score >= 40 else "EN RIESGO")
                    _ds_bg = "rgba(52,211,153,0.1)" if _div_score >= 70 else ("rgba(251,191,36,0.1)" if _div_score >= 40 else "rgba(248,113,113,0.1)")

                    # Score badge
                    st.markdown(f"""
                    <div style='text-align:center;margin-bottom:16px;'>
                      <span style='background:{_ds_bg};border:2px solid {_ds_color};border-radius:50%;
                                   display:inline-block;width:80px;height:80px;line-height:80px;
                                   font-size:28px;font-weight:800;color:{_ds_color};'>{_div_score}</span>
                      <div style='color:{_ds_color};font-size:14px;font-weight:700;margin-top:8px;'>{_ds_label}</div>
                    </div>""", unsafe_allow_html=True)

                    _dk1, _dk2, _dk3, _dk4 = st.columns(4)
                    _dk1.markdown(kpi("Dividend Safety", f"{_div_score}/100", _ds_label,
                                      "green" if _div_score >= 70 else ("yellow" if _div_score >= 40 else "red")),
                                 unsafe_allow_html=True)
                    _dk2.markdown(kpi("Div Yield", f"{_div_yield_g7:.2f}%", "", "green"), unsafe_allow_html=True)
                    _dk3.markdown(kpi("Payout Ratio", f"{_payout_pct:.1f}%", "< 60% ideal",
                                      "green" if _payout_pct < 60 else "red"), unsafe_allow_html=True)
                    _dk4.markdown(kpi("Debt/Equity", f"{_debt_equity_ratio:.2f}", "< 1.0 ideal",
                                      "green" if _debt_equity_ratio < 1 else "red"), unsafe_allow_html=True)

                    # Breakdown table
                    _tbl_html = """<table style='width:100%;border-collapse:collapse;margin-top:12px;'>
                        <tr style='border-bottom:1px solid #1a1a1a;'>
                            <th style='padding:8px;color:#5a6f8a;text-align:left;font-size:11px;'>CRITERIO</th>
                            <th style='padding:8px;color:#5a6f8a;text-align:center;font-size:11px;'>VALOR</th>
                            <th style='padding:8px;color:#5a6f8a;text-align:center;font-size:11px;'>IDEAL</th>
                            <th style='padding:8px;color:#5a6f8a;text-align:center;font-size:11px;'>PUNTOS</th>
                        </tr>"""
                    for _cr, _val, _ideal, _pts in _breakdown:
                        _tbl_html += f"""<tr style='border-bottom:1px solid #111;'>
                            <td style='padding:8px;color:#c8d6e5;font-size:12px;'>{_cr}</td>
                            <td style='padding:8px;color:#f0f6ff;text-align:center;font-size:12px;font-weight:600;'>{_val}</td>
                            <td style='padding:8px;color:#5a6f8a;text-align:center;font-size:12px;'>{_ideal}</td>
                            <td style='padding:8px;color:#94a3b8;text-align:center;font-size:12px;font-weight:600;'>{_pts}</td>
                        </tr>"""
                    _tbl_html += "</table>"
                    st.markdown(_tbl_html, unsafe_allow_html=True)
                else:
                    st.info("Esta empresa no paga dividendos actualmente.")
            except Exception as _e_g7:
                st.info(f"No se pudo calcular dividend safety: {_e_g7}")

        # ── J2: DCA Simulator ──
        with st.expander("💰 Simulador DCA (Dollar Cost Averaging)", expanded=False):
            try:
                _dca_c1, _dca_c2, _dca_c3 = st.columns(3)
                _dca_amount = _dca_c1.number_input("Aporte mensual ($)", min_value=10.0, value=500.0, step=50.0, key="dca_amount")
                _dca_years = _dca_c2.number_input("Anos", min_value=1, max_value=20, value=5, key="dca_years")
                _dca_ticker = _dca_c3.text_input("Ticker", value=ticker_solo, key="dca_ticker")

                if st.button("Simular DCA", key="dca_run"):
                    with st.spinner("Simulando DCA..."):
                        _dca_hist = yf.download(_dca_ticker.strip().upper(), period=f"{_dca_years}y", interval="1mo", progress=False)
                        if _dca_hist is not None and len(_dca_hist) > 2:
                            if isinstance(_dca_hist.columns, pd.MultiIndex):
                                _dca_prices = _dca_hist["Close"].iloc[:, 0]
                            else:
                                _dca_prices = _dca_hist["Close"]

                            # DCA simulation
                            _dca_shares_total = 0.0
                            _dca_invested = 0.0
                            _dca_values = []
                            _dca_invested_vals = []
                            _dca_dates = []
                            for _idx, _p in enumerate(_dca_prices):
                                if _p > 0:
                                    _dca_shares_total += _dca_amount / _p
                                    _dca_invested += _dca_amount
                                    _dca_values.append(_dca_shares_total * _p)
                                    _dca_invested_vals.append(_dca_invested)
                                    _dca_dates.append(_dca_prices.index[_idx])

                            # Lump sum comparison
                            _lump_shares = (_dca_amount * len(_dca_prices)) / _dca_prices.iloc[0] if _dca_prices.iloc[0] > 0 else 0
                            _lump_values = [_lump_shares * _p for _p in _dca_prices]

                            _dca_final = _dca_values[-1] if _dca_values else 0
                            _lump_final = _lump_values[-1] if _lump_values else 0
                            _lump_invested = _dca_amount * len(_dca_prices)
                            _dca_return = ((_dca_final / _dca_invested - 1) * 100) if _dca_invested > 0 else 0
                            _lump_return = ((_lump_final / _lump_invested - 1) * 100) if _lump_invested > 0 else 0

                            _dk1, _dk2, _dk3, _dk4, _dk5 = st.columns(5)
                            _dk1.markdown(kpi("Total Invertido", f"${_dca_invested:,.0f}", f"{len(_dca_values)} aportes", "blue"),
                                         unsafe_allow_html=True)
                            _dk2.markdown(kpi("Valor DCA", f"${_dca_final:,.0f}", f"{ticker_solo}",
                                              "green" if _dca_return > 0 else "red"), unsafe_allow_html=True)
                            _dk3.markdown(kpi("DCA Retorno", f"{_dca_return:+.1f}%", "Dollar Cost Avg",
                                              "green" if _dca_return > 0 else "red"), unsafe_allow_html=True)
                            _dk4.markdown(kpi("Valor Lump Sum", f"${_lump_final:,.0f}", "Inversion unica", "purple"),
                                         unsafe_allow_html=True)
                            _dk5.markdown(kpi("Lump Sum Retorno", f"{_lump_return:+.1f}%", "Todo el dia 1",
                                              "green" if _lump_return > 0 else "red"), unsafe_allow_html=True)

                            # Chart
                            _fig_dca = go.Figure()
                            _fig_dca.add_trace(go.Scatter(x=_dca_dates, y=_dca_values, mode="lines",
                                                          name="DCA", line=dict(color="#60a5fa", width=2)))
                            _fig_dca.add_trace(go.Scatter(x=_dca_dates, y=_dca_invested_vals, mode="lines",
                                                          name="Invertido", line=dict(color="#5a6f8a", width=1.5, dash="dot")))
                            _fig_dca.add_trace(go.Scatter(x=list(_dca_prices.index), y=_lump_values, mode="lines",
                                                          name="Lump Sum", line=dict(color="#a78bfa", width=1.5)))
                            _fig_dca.update_layout(**DARK, height=350,
                                title=dict(text=f"DCA vs Lump Sum — {_dca_ticker.upper()}", font=dict(color="#94a3b8", size=13), x=0.5),
                                legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"),
                                yaxis_title="Valor ($)")
                            st.plotly_chart(_fig_dca, use_container_width=True)
                        else:
                            st.warning("No hay suficientes datos historicos para simular.")
            except Exception as _e_dca:
                st.warning(f"Error en simulador DCA: {_e_dca}")

        # ── ML Analysis (Machine Learning) ──
        with st.expander("🧠 Analisis ML (Machine Learning)", expanded=False):
            try:
                if not ml_engine.HAS_SKLEARN:
                    st.info("Instala scikit-learn para usar el motor ML: pip install scikit-learn")
                else:
                    _quality_ml, _anomaly_ml, _scorer_ml = ml_engine.get_models()
                    if _quality_ml is not None and not _quality_ml.trained:
                        st.info("Los modelos ML no estan entrenados. Haz clic en el boton para entrenarlos.")
                        if st.button("🚀 Entrenar Modelos ML", key="ml_train"):
                            _prog = st.progress(0, text="Entrenando modelos ML...")
                            def _ml_progress(p):
                                _prog.progress(min(p, 1.0), text=f"Recolectando datos... {p*100:.0f}%")
                            _ok = ml_engine.train_models(progress_callback=_ml_progress)
                            _prog.empty()
                            if _ok:
                                st.success("Modelos ML entrenados exitosamente.")
                                st.rerun()
                            else:
                                st.error("Error entrenando modelos. Verifica conexion a internet.")
                    elif _quality_ml is not None and _quality_ml.trained:
                        with st.spinner("Analizando con ML..."):
                            _ml_result = ml_engine.analyze_ticker(ticker_solo)
                        if _ml_result:
                            # Quality classification badge
                            _ql = _ml_result['quality_label']
                            _qc = _ml_result['quality_confidence']
                            _badge_colors = {"EXCELENTE": "#34d399", "BUENA": "#60a5fa", "REGULAR": "#fbbf24", "DEBIL": "#f87171"}
                            _badge_bg = {"EXCELENTE": "#064e3b", "BUENA": "#0d1f35", "REGULAR": "#422006", "DEBIL": "#451a03"}
                            _bc = _badge_colors.get(_ql, "#94a3b8")
                            _bg = _badge_bg.get(_ql, "#0a0a0a")

                            _ml1, _ml2 = st.columns(2)
                            with _ml1:
                                st.markdown(f"""
                                <div style='background:{_bg};border:2px solid {_bc};border-radius:14px;padding:20px;text-align:center;'>
                                  <div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1px;'>Clasificacion ML</div>
                                  <div style='font-size:28px;font-weight:800;color:{_bc};margin:8px 0;'>{_ql}</div>
                                  <div style='font-size:13px;color:#64748b;'>Confianza: {_qc}%</div>
                                </div>""", unsafe_allow_html=True)
                            with _ml2:
                                # Smart Score gauge
                                _ss = _ml_result['smart_score']
                                _ss_color = "#34d399" if _ss >= 65 else ("#fbbf24" if _ss >= 40 else "#f87171")
                                _fig_ss = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=_ss,
                                    number=dict(suffix="/100", font=dict(color="#f0f6ff", size=28)),
                                    title=dict(text="Smart Score ML", font=dict(color="#94a3b8", size=14)),
                                    gauge=dict(
                                        axis=dict(range=[0, 100], tickcolor="#475569",
                                                  tickfont=dict(color="#475569", size=10)),
                                        bar=dict(color=_ss_color, thickness=0.7),
                                        bgcolor="#0a0a0a", bordercolor="#1a1a1a",
                                        steps=[
                                            dict(range=[0, 40], color="rgba(248,113,113,0.1)"),
                                            dict(range=[40, 65], color="rgba(251,191,36,0.1)"),
                                            dict(range=[65, 100], color="rgba(52,211,153,0.1)"),
                                        ],
                                    )
                                ))
                                _fig_ss.update_layout(**dark_layout(height=250, margin=dict(l=20, r=20, t=50, b=10)))
                                st.plotly_chart(_fig_ss, use_container_width=True)

                            # Anomalies table
                            _anomalies = _ml_result.get('anomalies', [])
                            if _anomalies:
                                st.markdown("<div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1px;font-weight:600;margin:16px 0 8px;'>Anomalias Detectadas</div>", unsafe_allow_html=True)
                                for _a in _anomalies:
                                    _az = _a['z_score']
                                    _ac = "#f87171" if _az > 2.5 else "#fbbf24"
                                    st.markdown(f"""
                                    <div style='background:#0a0a0a;border-left:3px solid {_ac};border-radius:0 8px 8px 0;
                                                padding:8px 14px;margin-bottom:6px;display:flex;justify-content:space-between;'>
                                      <span style='color:#94a3b8;font-size:12px;'>⚠️ <b>{_a['metric']}</b> — {_a['direction']} del promedio</span>
                                      <span style='color:{_ac};font-size:12px;font-weight:600;'>Z-Score: {_az} | Valor: {_a['value']:.4f}</span>
                                    </div>""", unsafe_allow_html=True)

                            # Feature importance bar chart
                            _fi = _ml_result.get('feature_importance', {})
                            if _fi:
                                _fi_sorted = dict(sorted(_fi.items(), key=lambda x: x[1], reverse=True))
                                _fig_fi = go.Figure(go.Bar(
                                    x=list(_fi_sorted.values()), y=list(_fi_sorted.keys()),
                                    orientation='h', marker_color="#60a5fa",
                                    text=[f"{v:.3f}" for v in _fi_sorted.values()],
                                    textposition="outside", textfont=dict(color="#94a3b8", size=10),
                                ))
                                _fig_fi.update_layout(**DARK, height=350,
                                    title=dict(text="Importancia de Factores (ML)", font=dict(color="#94a3b8", size=13), x=0.5),
                                    showlegend=False, yaxis=dict(autorange="reversed"),
                                    margin=dict(l=100, r=40, t=40, b=20))
                                st.plotly_chart(_fig_fi, use_container_width=True)
                        else:
                            st.info("No se pudo analizar este ticker con ML.")

                        # Retrain button
                        if st.button("🔄 Re-entrenar Modelos ML", key="ml_retrain"):
                            try:
                                import shutil
                                _cache = ml_engine.MODEL_DIR / "training_data.pkl"
                                if _cache.exists():
                                    _cache.unlink()
                            except Exception:
                                pass
                            _prog2 = st.progress(0, text="Re-entrenando...")
                            def _ml_prog2(p):
                                _prog2.progress(min(p, 1.0), text=f"Recolectando datos... {p*100:.0f}%")
                            _ok2 = ml_engine.train_models(progress_callback=_ml_prog2)
                            _prog2.empty()
                            if _ok2:
                                st.success("Modelos re-entrenados.")
                                st.rerun()
                            else:
                                st.error("Error re-entrenando modelos.")
            except Exception as _e_ml:
                st.warning(f"Error en analisis ML: {_e_ml}")

        # ── Institutional News (Timeline) ──
        with st.expander("📰 Noticias Institucionales", expanded=False):
            try:
                _tradingview_news(ticker_solo)
            except Exception:
                st.info("No se pudieron cargar noticias.")

        # ── News Monitor with Sentiment (Bloomberg-style) ──
        with st.expander("📰 Noticias y Sentimiento", expanded=False):
            try:
                if yf is not None:
                    _tk_news = yf.Ticker(ticker_solo)
                    _news_items = getattr(_tk_news, "news", None) or []
                    if _news_items:
                        _pos_words = {"surge","jump","gain","rise","bull","profit","beat","upgrade",
                                      "record","boost","high","rally","strong","growth","up","buy","positive"}
                        _neg_words = {"fall","drop","crash","loss","bear","miss","downgrade","cut",
                                      "low","decline","weak","risk","sell","negative","down","plunge","fear"}
                        _pos_count = 0
                        _neg_count = 0
                        for _art in _news_items[:15]:
                            _title = (_art.get("title") or "").lower()
                            _pub = _art.get("publisher", "Unknown")
                            _link = _art.get("link", "#")
                            _ts = _art.get("providerPublishTime")
                            _date_str = ""
                            if _ts:
                                try:
                                    from datetime import timezone
                                    _date_str = datetime.fromtimestamp(_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                                except Exception:
                                    _date_str = str(_ts)
                            # Count sentiment words
                            _title_words = set(_title.split())
                            _p = len(_title_words & _pos_words)
                            _n = len(_title_words & _neg_words)
                            _pos_count += _p
                            _neg_count += _n
                            if _p > _n:
                                _badge = "<span style='color:#34d399;font-weight:600;'>POSITIVO</span>"
                            elif _n > _p:
                                _badge = "<span style='color:#f87171;font-weight:600;'>NEGATIVO</span>"
                            else:
                                _badge = "<span style='color:#94a3b8;font-weight:600;'>NEUTRAL</span>"
                            st.markdown(f"""
                            <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:10px;
                                        padding:12px 16px;margin-bottom:8px;'>
                              <div style='font-size:13px;color:#f0f6ff;font-weight:600;'>
                                <a href='{_link}' target='_blank' style='color:#60a5fa;text-decoration:none;'>{_art.get("title","Sin titulo")}</a>
                              </div>
                              <div style='font-size:11px;color:#5a6f8a;margin-top:4px;'>
                                {_pub} · {_date_str} · {_badge}
                              </div>
                            </div>""", unsafe_allow_html=True)
                        # Overall sentiment summary
                        _total_s = _pos_count + _neg_count
                        if _total_s > 0:
                            _pct_pos = _pos_count / _total_s * 100
                            if _pct_pos >= 60:
                                _overall_c, _overall_l = "#34d399", "SENTIMIENTO POSITIVO"
                            elif _pct_pos <= 40:
                                _overall_c, _overall_l = "#f87171", "SENTIMIENTO NEGATIVO"
                            else:
                                _overall_c, _overall_l = "#fbbf24", "SENTIMIENTO MIXTO"
                        else:
                            _overall_c, _overall_l = "#94a3b8", "NEUTRAL"
                        st.markdown(f"""
                        <div style='background:rgba(96,165,250,0.06);border:1px solid rgba(96,165,250,0.2);
                                    border-radius:12px;padding:14px;text-align:center;margin-top:10px;'>
                          <span style='color:{_overall_c};font-size:16px;font-weight:700;'>{_overall_l}</span>
                          <span style='color:#5a6f8a;font-size:12px;margin-left:12px;'>
                            (+{_pos_count} positivas / -{_neg_count} negativas en {len(_news_items[:15])} noticias)
                          </span>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.info("No se encontraron noticias recientes para este ticker.")
            except Exception as _e_news:
                st.info(f"No se pudieron cargar noticias con sentimiento: {_e_news}")

        # ── WACC Calculator (Bloomberg-style) ──
        with st.expander("💰 WACC (Costo de Capital)", expanded=False):
            try:
                _wacc_data = valuation.compute_wacc(ticker_solo)
                if _wacc_data and _wacc_data.get("wacc") is not None:
                    _wc1, _wc2, _wc3, _wc4 = st.columns(4)
                    _wc1.markdown(kpi("WACC", f"{_wacc_data['wacc']*100:.2f}%", "Costo de Capital", "purple"), unsafe_allow_html=True)
                    _wc2.markdown(kpi("Ke (Costo Equity)", f"{_wacc_data['ke']*100:.2f}%", f"Rf={_wacc_data['rf']*100:.1f}% + β×ERP", "blue"), unsafe_allow_html=True)
                    _wc3.markdown(kpi("Kd (Costo Deuda)", f"{_wacc_data['kd']*100:.2f}%", f"After-tax: {_wacc_data['kd']*(1-_wacc_data['tax_rate'])*100:.2f}%", "blue"), unsafe_allow_html=True)
                    _wc4.markdown(kpi("Tasa Impositiva", f"{_wacc_data['tax_rate']*100:.1f}%", "", "blue"), unsafe_allow_html=True)
                    _wc5, _wc6, _wc7, _wc8 = st.columns(4)
                    _wc5.markdown(kpi("Beta", f"{_wacc_data['beta']:.2f}", "", "blue"), unsafe_allow_html=True)
                    _wc6.markdown(kpi("Risk-Free Rate", f"{_wacc_data['rf']*100:.2f}%", "Treasury 10Y", "green"), unsafe_allow_html=True)
                    _wc7.markdown(kpi("Peso Equity", f"{_wacc_data['we']*100:.1f}%", fmt(_wacc_data['market_cap']), "purple"), unsafe_allow_html=True)
                    _wc8.markdown(kpi("Peso Deuda", f"{_wacc_data['wd']*100:.1f}%", fmt(_wacc_data['total_debt']), "red"), unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style='background:rgba(167,139,250,0.06);border:1px solid rgba(167,139,250,0.2);
                                border-radius:12px;padding:14px;color:#94a3b8;font-size:12px;margin-top:8px;'>
                      <strong>Formula:</strong> WACC = (E/V × Ke) + (D/V × Kd × (1-T))<br>
                      = ({_wacc_data['we']*100:.1f}% × {_wacc_data['ke']*100:.2f}%) + ({_wacc_data['wd']*100:.1f}% × {_wacc_data['kd']*100:.2f}% × (1 - {_wacc_data['tax_rate']*100:.1f}%))
                      = <strong style='color:#a78bfa;'>{_wacc_data['wacc']*100:.2f}%</strong>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.info("No se pudo calcular el WACC. Datos financieros insuficientes.")
            except Exception as _e_wacc:
                st.warning(f"Error calculando WACC: {_e_wacc}")

        # ── Intraday Chart with Volume Profile (Bloomberg-style) ──
        with st.expander("📈 Gráfico Intraday", expanded=False):
            try:
                if yf is not None:
                    _intra = yf.download(ticker_solo, period="1d", interval="5m", progress=False)
                    if _intra is not None and not _intra.empty:
                        # Flatten multi-level columns if needed
                        if hasattr(_intra.columns, 'levels') and len(_intra.columns.levels) > 1:
                            _intra.columns = _intra.columns.get_level_values(0)
                        _open = _intra["Open"]
                        _high = _intra["High"]
                        _low = _intra["Low"]
                        _close = _intra["Close"]
                        _vol = _intra["Volume"]
                        # Compute VWAP
                        _typical = (_high + _low + _close) / 3
                        _cum_tp_vol = (_typical * _vol).cumsum()
                        _cum_vol = _vol.cumsum()
                        _vwap = _cum_tp_vol / _cum_vol.replace(0, float('nan'))

                        from plotly.subplots import make_subplots as _make_sub
                        _fig_intra = _make_sub(rows=2, cols=1, shared_xaxes=True,
                                               row_heights=[0.7, 0.3], vertical_spacing=0.03)
                        _fig_intra.add_trace(go.Candlestick(
                            x=_intra.index, open=_open, high=_high, low=_low, close=_close,
                            increasing_line_color="#34d399", decreasing_line_color="#f87171",
                            increasing_fillcolor="#34d399", decreasing_fillcolor="#f87171",
                            name="Precio",
                        ), row=1, col=1)
                        _fig_intra.add_trace(go.Scatter(
                            x=_intra.index, y=_vwap, mode="lines",
                            line=dict(color="#a78bfa", width=1.5, dash="dot"),
                            name="VWAP",
                        ), row=1, col=1)
                        _colors_vol = ["#34d399" if c >= o else "#f87171"
                                        for c, o in zip(_close, _open)]
                        _fig_intra.add_trace(go.Bar(
                            x=_intra.index, y=_vol, marker_color=_colors_vol,
                            opacity=0.5, name="Volumen",
                        ), row=2, col=1)
                        _fig_intra.update_layout(
                            **dark_layout(height=500, showlegend=True, xaxis_rangeslider_visible=False,
                                         title=dict(text=f"{ticker_solo} — Intraday 5min",
                                                    font=dict(color="#94a3b8", size=14), x=0.5),
                                         legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a",
                                                     font=dict(color="#94a3b8", size=10))),
                        )
                        _fig_intra.update_xaxes(gridcolor="#1a1a1a", linecolor="#1a1a1a")
                        _fig_intra.update_yaxes(gridcolor="#1a1a1a", linecolor="#1a1a1a")
                        st.plotly_chart(_fig_intra, use_container_width=True)
                    else:
                        st.info("No hay datos intraday disponibles (mercado cerrado o ticker sin datos).")
            except Exception as _e_intra:
                st.warning(f"Error cargando gráfico intraday: {_e_intra}")

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

        # ── FEATURE 10: Rolling Beta Analysis ──
        with st.expander("β Beta Rolling"):
            try:
                import numpy as _np
                bench_options = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Russell 2000": "^RUT"}
                bench_name = st.selectbox("Benchmark", list(bench_options.keys()),
                                          key="beta_bench_select")
                bench_sym = bench_options[bench_name]

                ticker_hist = yf.download(ticker_solo, period="2y", interval="1d", progress=False)
                bench_hist = yf.download(bench_sym, period="2y", interval="1d", progress=False)

                if not ticker_hist.empty and not bench_hist.empty:
                    # Handle multi-level columns from yfinance
                    if isinstance(ticker_hist.columns, pd.MultiIndex):
                        tk_close = ticker_hist["Close"].iloc[:, 0]
                    else:
                        tk_close = ticker_hist["Close"]
                    if isinstance(bench_hist.columns, pd.MultiIndex):
                        bm_close = bench_hist["Close"].iloc[:, 0]
                    else:
                        bm_close = bench_hist["Close"]

                    tk_ret = tk_close.pct_change().dropna()
                    bm_ret = bm_close.pct_change().dropna()

                    # Align dates
                    common = tk_ret.index.intersection(bm_ret.index)
                    tk_ret = tk_ret.loc[common]
                    bm_ret = bm_ret.loc[common]

                    # Rolling 60-day beta
                    window = 60
                    rolling_cov = tk_ret.rolling(window).cov(bm_ret)
                    rolling_var = bm_ret.rolling(window).var()
                    rolling_beta = (rolling_cov / rolling_var).dropna()

                    if len(rolling_beta) > 0:
                        current_beta = rolling_beta.iloc[-1]
                        one_year_beta = rolling_beta.tail(252)
                        avg_beta = one_year_beta.mean()
                        min_beta = rolling_beta.min()
                        max_beta = rolling_beta.max()

                        bk1, bk2, bk3, bk4 = st.columns(4)
                        beta_color = "green" if 0.8 <= current_beta <= 1.2 else "red"
                        bk1.markdown(kpi("Beta Actual", f"{current_beta:.2f}",
                                         f"vs {bench_name}", beta_color), unsafe_allow_html=True)
                        bk2.markdown(kpi("Beta Prom. 1Y", f"{avg_beta:.2f}", "",
                                         "blue"), unsafe_allow_html=True)
                        bk3.markdown(kpi("Beta Mín.", f"{min_beta:.2f}", "",
                                         "blue"), unsafe_allow_html=True)
                        bk4.markdown(kpi("Beta Máx.", f"{max_beta:.2f}", "",
                                         "blue"), unsafe_allow_html=True)

                        fig_beta = go.Figure()
                        fig_beta.add_trace(go.Scatter(
                            x=rolling_beta.index, y=rolling_beta.values,
                            mode="lines", name="Rolling Beta (60d)",
                            line=dict(color="#60a5fa", width=2),
                        ))
                        fig_beta.add_hline(y=1.0, line_dash="dot", line_color="#fbbf24",
                                           annotation_text="Beta = 1.0",
                                           annotation_font_color="#fbbf24")
                        fig_beta.update_layout(**DARK, height=350,
                            title=dict(text=f"Rolling Beta (60d) vs {bench_name}",
                                       font=dict(color="#94a3b8", size=13), x=0.5),
                            yaxis_title="Beta", showlegend=False)
                        st.plotly_chart(fig_beta, use_container_width=True)
                    else:
                        st.info("Datos insuficientes para calcular el rolling beta.")
                else:
                    st.info("No se pudieron descargar datos históricos.")
            except Exception as e:
                st.warning(f"Error calculando rolling beta: {e}")

        # ── FEATURE 13: ESG Scores ──
        with st.expander("🌱 ESG (Sostenibilidad)"):
            try:
                tk_esg = yf.Ticker(ticker_solo)
                esg_data = tk_esg.sustainability
                if esg_data is not None and not esg_data.empty:
                    esg_dict = esg_data.to_dict()
                    if isinstance(esg_dict, dict):
                        first_key = list(esg_dict.keys())[0] if esg_dict else None
                        if first_key and isinstance(esg_dict[first_key], dict):
                            esg_vals = esg_dict[first_key]
                        else:
                            esg_vals = esg_dict
                    else:
                        esg_vals = {}

                    env_score_val = esg_vals.get("environmentScore") or esg_vals.get("Environment Score")
                    soc_score_val = esg_vals.get("socialScore") or esg_vals.get("Social Score")
                    gov_score_val = esg_vals.get("governanceScore") or esg_vals.get("Governance Score")
                    total_esg = esg_vals.get("totalEsg") or esg_vals.get("Total ESG Score")
                    esg_perf = esg_vals.get("esgPerformance") or esg_vals.get("ESG Performance")

                    if total_esg is not None:
                        try:
                            total_val = float(total_esg)
                        except (TypeError, ValueError):
                            total_val = 0

                        if total_val <= 10:
                            esg_rating = "Negligible Risk"
                            esg_color = "#34d399"
                        elif total_val <= 20:
                            esg_rating = "Low Risk"
                            esg_color = "#34d399"
                        elif total_val <= 30:
                            esg_rating = "Medium Risk"
                            esg_color = "#fbbf24"
                        elif total_val <= 40:
                            esg_rating = "High Risk"
                            esg_color = "#f87171"
                        else:
                            esg_rating = "Severe Risk"
                            esg_color = "#f87171"

                        st.markdown(f"""
                        <div style='text-align:center;margin-bottom:16px;'>
                          <div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1px;'>
                            ESG Risk Rating</div>
                          <div style='font-size:28px;font-weight:800;color:{esg_color};margin:4px 0;'>
                            {total_val:.1f}</div>
                          <div style='font-size:14px;font-weight:600;color:{esg_color};'>{esg_rating}</div>
                          {f"<div style='font-size:11px;color:#475569;margin-top:4px;'>Performance: {esg_perf}</div>" if esg_perf else ""}
                        </div>""", unsafe_allow_html=True)

                        esg_scores_list = [
                            ("🌍 Environment", env_score_val, "#34d399"),
                            ("👥 Social", soc_score_val, "#60a5fa"),
                            ("🏛️ Governance", gov_score_val, "#a78bfa"),
                        ]
                        for esg_label, esg_val, esg_bar_color in esg_scores_list:
                            if esg_val is not None:
                                try:
                                    v = float(esg_val)
                                except (TypeError, ValueError):
                                    continue
                                pct = min(v / 30 * 100, 100)
                                st.markdown(f"""
                                <div style='margin-bottom:12px;'>
                                  <div style='display:flex;justify-content:space-between;margin-bottom:4px;'>
                                    <span style='color:#94a3b8;font-size:13px;'>{esg_label}</span>
                                    <span style='color:{esg_bar_color};font-weight:600;font-size:13px;'>{v:.1f}</span>
                                  </div>
                                  <div style='background:#1a1a1a;border-radius:6px;height:10px;overflow:hidden;'>
                                    <div style='background:{esg_bar_color};width:{pct}%;height:100%;border-radius:6px;
                                                transition:width 0.5s ease;'></div>
                                  </div>
                                </div>""", unsafe_allow_html=True)
                    else:
                        st.info("Datos ESG disponibles pero sin puntuación total. Datos crudos:")
                        st.dataframe(esg_data, use_container_width=True)
                else:
                    st.info("No hay datos ESG disponibles para este ticker. "
                            "No todas las empresas tienen puntuaciones ESG en yfinance.")
            except Exception as e:
                st.warning(f"Error obteniendo datos ESG: {e}")

        # ── MULTI-SOURCE DATA INTELLIGENCE ──
        try:
            from data_sources import get_aggregator
            _agg = get_aggregator()

            with st.expander("🏛️ Holders Institucionales", expanded=False):
                try:
                    inst_holders = _agg.get_institutional_holders(ticker_solo)
                    if inst_holders is not None and not inst_holders.empty:
                        st.markdown(f"""
                        <div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1.5px;
                                    font-weight:600;margin-bottom:12px;'>
                            TOP INSTITUTIONAL HOLDERS — {ticker_solo}</div>
                        """, unsafe_allow_html=True)
                        st.dataframe(
                            inst_holders.style.set_properties(**{
                                "background-color": "#0a0a0a",
                                "color": "#c8d6e5",
                                "border-color": "#1a1a1a",
                            }),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("No se encontraron datos de holders institucionales para este ticker.")
                except Exception as e_inst:
                    st.warning(f"Error obteniendo holders institucionales: {e_inst}")

            with st.expander("📊 Flujo de Opciones", expanded=False):
                try:
                    opts = _agg.get_options_flow(ticker_solo)
                    if opts:
                        st.markdown(f"""
                        <div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1.5px;
                                    font-weight:600;margin-bottom:12px;'>
                            OPTIONS FLOW — {ticker_solo} (proximas {len(opts)} expiraciones)</div>
                        """, unsafe_allow_html=True)

                        opt_df = pd.DataFrame(opts)

                        # Put/Call ratio bar chart
                        fig_opts = go.Figure()
                        fig_opts.add_trace(go.Bar(
                            x=opt_df["expiry"], y=opt_df["calls_vol"],
                            name="Calls Vol", marker_color="#34d399",
                        ))
                        fig_opts.add_trace(go.Bar(
                            x=opt_df["expiry"], y=opt_df["puts_vol"],
                            name="Puts Vol", marker_color="#f87171",
                        ))
                        fig_opts.update_layout(
                            **DARK, height=300, barmode="group",
                            title=dict(
                                text="Volumen Calls vs Puts por Expiracion",
                                font=dict(color="#94a3b8", size=13), x=0.5,
                            ),
                            legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"),
                            xaxis_title="Fecha Expiracion",
                            yaxis_title="Volumen",
                        )
                        st.plotly_chart(fig_opts, use_container_width=True)

                        # Ratio summary
                        for o in opts:
                            ratio = o["put_call_ratio"]
                            if ratio > 1.0:
                                r_color = "#f87171"
                                r_label = "Bearish"
                            elif ratio > 0.7:
                                r_color = "#fbbf24"
                                r_label = "Neutral"
                            else:
                                r_color = "#34d399"
                                r_label = "Bullish"
                            st.markdown(f"""
                            <div style='display:inline-block;margin-right:16px;padding:8px 14px;
                                        background:rgba(30,30,30,0.6);border:1px solid #1a1a1a;
                                        border-radius:10px;margin-bottom:8px;'>
                              <span style='color:#64748b;font-size:11px;'>Exp {o["expiry"]}</span>
                              <span style='color:{r_color};font-weight:700;margin-left:8px;'>
                                P/C: {ratio:.3f}</span>
                              <span style='color:{r_color};font-size:11px;margin-left:4px;'>({r_label})</span>
                            </div>""", unsafe_allow_html=True)
                    else:
                        st.info("No hay datos de opciones disponibles para este ticker.")
                except Exception as e_opts:
                    st.warning(f"Error obteniendo flujo de opciones: {e_opts}")

            with st.expander("👤 Insider Trading", expanded=False):
                try:
                    insiders = _agg.get_insider_trades(ticker_solo)
                    if insiders is not None and not insiders.empty:
                        st.markdown(f"""
                        <div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;letter-spacing:1.5px;
                                    font-weight:600;margin-bottom:12px;'>
                            INSIDER TRANSACTIONS — {ticker_solo}</div>
                        """, unsafe_allow_html=True)
                        st.dataframe(
                            insiders.style.set_properties(**{
                                "background-color": "#0a0a0a",
                                "color": "#c8d6e5",
                                "border-color": "#1a1a1a",
                            }),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("No se encontraron transacciones de insiders. "
                                "Asegurate de tener instalado finvizfinance (pip install finvizfinance).")
                except Exception as e_ins:
                    st.warning(f"Error obteniendo insider trading: {e_ins}")

        except ImportError:
            pass  # data_sources module not available
        except Exception:
            pass  # graceful degradation

        # ── B6: Sensitivity Table DCF ──
        with st.expander("📊 Tabla de Sensibilidad DCF", expanded=False):
            try:
                if st.button("Calcular Sensibilidad", key="btn_sensitivity_dcf"):
                    with st.spinner("Calculando DCF profesional y tabla de sensibilidad…"):
                        _dcf_pro = valuation.compute_dcf_professional(ticker_solo)
                    if _dcf_pro and _dcf_pro.get("sensitivity"):
                        _sens = _dcf_pro["sensitivity"]
                        _wacc_vals = _dcf_pro.get("wacc_range", [])
                        _g_vals = _dcf_pro.get("g_range", [])
                        _base_fv = _dcf_pro.get("fair_value_per_share", 0)
                        _curr_price_b6 = _dcf_pro.get("current_price", 0)
                        _base_wacc = _dcf_pro.get("wacc", 0.10)
                        _base_g = _dcf_pro.get("terminal_g", 0.03)

                        st.markdown(f"""
                        <div style='text-align:center;margin-bottom:12px;'>
                          <span style='color:#60a5fa;font-size:14px;font-weight:600;'>
                            Fair Value Base: ${_base_fv:,.2f}</span>
                          <span style='color:#5a6f8a;font-size:12px;margin-left:16px;'>
                            WACC: {_base_wacc*100:.2f}% · g: {_base_g*100:.1f}%</span>
                          <span style='color:#fbbf24;font-size:12px;margin-left:16px;'>
                            Precio Actual: ${_curr_price_b6:,.2f}</span>
                        </div>""", unsafe_allow_html=True)

                        # Build 5x5 grid for heatmap
                        _wacc_pcts = [round(w * 100, 2) for w in _wacc_vals]
                        _g_pcts = [round(g * 100, 2) for g in _g_vals]
                        _z_matrix = []
                        _text_matrix = []
                        for _w_pct in _wacc_pcts:
                            _row_z = []
                            _row_txt = []
                            for _g_pct in _g_pcts:
                                _val = _sens.get((_w_pct, _g_pct))
                                if _val is not None:
                                    _row_z.append(_val)
                                    _row_txt.append(f"${_val:,.2f}")
                                else:
                                    _row_z.append(0)
                                    _row_txt.append("N/A")
                            _z_matrix.append(_row_z)
                            _text_matrix.append(_row_txt)

                        # Custom colorscale: green if above price, red if below
                        _custom_cs = [[0, "#f87171"], [0.5, "#fbbf24"], [1, "#34d399"]]
                        if _curr_price_b6 > 0:
                            _all_vals = [v for row in _z_matrix for v in row if v > 0]
                            if _all_vals:
                                _vmin = min(_all_vals)
                                _vmax = max(_all_vals)
                                if _vmax > _vmin:
                                    _mid = (_curr_price_b6 - _vmin) / (_vmax - _vmin)
                                    _mid = max(0.01, min(0.99, _mid))
                                    _custom_cs = [
                                        [0, "#f87171"],
                                        [_mid, "#fbbf24"],
                                        [1, "#34d399"],
                                    ]

                        _fig_sens = go.Figure(data=go.Heatmap(
                            z=_z_matrix,
                            x=[f"g={g}%" for g in _g_pcts],
                            y=[f"WACC={w}%" for w in _wacc_pcts],
                            text=_text_matrix,
                            texttemplate="%{text}",
                            textfont=dict(size=11, color="#f0f6ff"),
                            colorscale=_custom_cs,
                            hoverongaps=False,
                            showscale=True,
                            colorbar=dict(
                                title="Fair Value",
                                titlefont=dict(color="#94a3b8"),
                                tickfont=dict(color="#94a3b8"),
                            ),
                        ))
                        _fig_sens.update_layout(
                            **dark_layout(
                                height=400,
                                title=dict(text="Sensibilidad DCF: WACC vs Tasa de Crecimiento Terminal",
                                           font=dict(color="#94a3b8", size=14), x=0.5),
                                xaxis=dict(title="Crecimiento Terminal (g)", side="bottom",
                                           tickfont=dict(color="#94a3b8")),
                                yaxis=dict(title="WACC", tickfont=dict(color="#94a3b8")),
                            ),
                        )
                        if _curr_price_b6 > 0:
                            _fig_sens.add_annotation(
                                text=f"Precio Actual: ${_curr_price_b6:,.2f}",
                                xref="paper", yref="paper", x=1.0, y=-0.15,
                                showarrow=False, font=dict(color="#fbbf24", size=12),
                            )
                        st.plotly_chart(_fig_sens, use_container_width=True)
                    else:
                        st.info("No se pudo calcular la tabla de sensibilidad DCF. Datos insuficientes.")
            except Exception as _e_b6:
                st.warning(f"Error calculando sensibilidad DCF: {_e_b6}")

        # ── Monte Carlo DCF ──
        with st.expander("🎲 Monte Carlo DCF — Simulacion Probabilistica", expanded=False):
            try:
                _mc_c1, _mc_c2, _mc_c3 = st.columns(3)
                _mc_ws = _mc_c1.slider("σ WACC (%)", 0.5, 3.0, 1.0, 0.1, key="mc_wacc") / 100
                _mc_gs = _mc_c2.slider("σ Crecimiento (%)", 0.5, 5.0, 2.0, 0.5, key="mc_growth") / 100
                _mc_ts = _mc_c3.slider("σ Terminal g (%)", 0.1, 1.5, 0.5, 0.1, key="mc_g") / 100
                if st.button("🎲 Ejecutar 1,000 Simulaciones", key="mc_run"):
                    with st.spinner("Ejecutando Monte Carlo DCF…"):
                        _mc = valuation.monte_carlo_dcf(ticker_solo, 1000, _mc_ws, _mc_gs, _mc_ts)
                    if _mc is None:
                        st.warning("No se pudo ejecutar Monte Carlo. Datos insuficientes.")
                    else:
                        _pc = "#34d399" if _mc["prob_above_price"] >= 50 else "#f87171"
                        _k1, _k2, _k3, _k4 = st.columns(4)
                        for _col, _lbl, _val, _clr in [
                            (_k1, "P(FV > Precio)", f"{_mc['prob_above_price']:.1f}%", _pc),
                            (_k2, "P(Upside > 20%)", f"{_mc['prob_20pct_upside']:.1f}%", "#60a5fa"),
                            (_k3, "Mediana FV", f"${_mc['median']:,.2f}", "#e2e8f0"),
                            (_k4, "IC 90%", f"${_mc['p5']:,.0f}-${_mc['p95']:,.0f}", "#e2e8f0"),
                        ]:
                            _col.markdown(f"<div style='background:#0a0a0a;border-radius:8px;padding:12px;text-align:center;border:1px solid #1a1a1a'>"
                                          f"<div style='color:#94a3b8;font-size:11px'>{_lbl}</div>"
                                          f"<div style='color:{_clr};font-size:22px;font-weight:700'>{_val}</div></div>", unsafe_allow_html=True)
                        _fv = _mc["fair_values"]
                        _above = _fv[_fv >= _mc["current_price"]]
                        _below = _fv[_fv < _mc["current_price"]]
                        import plotly.graph_objects as _mcgo
                        _fig_mc = _mcgo.Figure()
                        _fig_mc.add_trace(_mcgo.Histogram(x=_below, nbinsx=30, name="< Precio", marker_color="#f87171", opacity=0.7))
                        _fig_mc.add_trace(_mcgo.Histogram(x=_above, nbinsx=30, name="> Precio", marker_color="#34d399", opacity=0.7))
                        _fig_mc.add_vline(x=_mc["current_price"], line_dash="dash", line_color="#fbbf24", line_width=2,
                                          annotation_text=f"Precio: ${_mc['current_price']:,.2f}", annotation_font_color="#fbbf24")
                        _fig_mc.add_vline(x=_mc["median"], line_dash="dot", line_color="#60a5fa", line_width=1,
                                          annotation_text=f"Mediana: ${_mc['median']:,.2f}", annotation_font_color="#60a5fa",
                                          annotation_position="top left")
                        _fig_mc.update_layout(**dark_layout(height=400,
                            title=dict(text=f"Distribucion Fair Value — {_mc['n_valid']} sims", font=dict(color="#94a3b8"), x=0.5),
                            xaxis=dict(title="Fair Value ($)"), yaxis=dict(title="Frecuencia"),
                            barmode="stack", showlegend=True,
                            legend=dict(x=0.01, y=0.99, bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"))))
                        st.plotly_chart(_fig_mc, use_container_width=True)
                        _fig_bx = _mcgo.Figure()
                        _fig_bx.add_trace(_mcgo.Box(x=_fv, name="Fair Values", marker_color="#3b82f6", boxpoints="outliers"))
                        _fig_bx.add_vline(x=_mc["current_price"], line_dash="dash", line_color="#fbbf24", line_width=2)
                        _fig_bx.update_layout(**dark_layout(height=180, xaxis=dict(title="Fair Value ($)"), showlegend=False))
                        st.plotly_chart(_fig_bx, use_container_width=True)
                        st.markdown(f"<div style='background:#0a0a0a;border-radius:8px;padding:16px;border:1px solid #1a1a1a'>"
                                    f"<b style='color:#e2e8f0'>Resumen</b><br>"
                                    f"<span style='color:#94a3b8'>Media: ${_mc['mean']:,.2f} | Std: ${_mc['std']:,.2f} | "
                                    f"P5: ${_mc['p5']:,.2f} | P95: ${_mc['p95']:,.2f} | "
                                    f"P(50%+ upside): {_mc['prob_50pct_upside']:.1f}%</span><br>"
                                    f"<small style='color:#475569'>WACC: {_mc['wacc_base']*100:.1f}% | Growth: {_mc['growth_base']*100:.1f}% | g: {_mc['g_base']*100:.1f}%</small></div>",
                                    unsafe_allow_html=True)
            except Exception as _e_mc:
                st.warning(f"Error en Monte Carlo: {_e_mc}")

        # ── B7: Multiples Dashboard ──
        with st.expander("📈 Dashboard de Múltiplos", expanded=False):
            try:
                if st.button("Calcular Múltiplos", key="btn_multiples_dashboard"):
                    with st.spinner("Calculando múltiplos de valoración…"):
                        _mult_result = valuation.compute_multiples(ticker_solo)
                    _multiples_list = _mult_result.get("multiples", [])
                    _mult_sector = _mult_result.get("sector", "N/A")
                    if _multiples_list:
                        st.markdown(f"""
                        <div style='text-align:center;margin-bottom:12px;'>
                          <span style='color:#94a3b8;font-size:12px;'>Sector: </span>
                          <span style='color:#60a5fa;font-size:13px;font-weight:600;'>{_mult_sector}</span>
                        </div>""", unsafe_allow_html=True)

                        _m_names = []
                        _m_values = []
                        _m_medians = []
                        _m_colors = []
                        _m_signals = []
                        for _m in _multiples_list:
                            if _m.get("value") is not None:
                                _m_names.append(_m["name"])
                                _m_values.append(round(_m["value"], 2))
                                _m_medians.append(_m.get("sector_median") or 0)
                                _m_colors.append(_m.get("color", "#fbbf24"))
                                _sig_label = {"cheap": "BARATO", "fair": "JUSTO", "expensive": "CARO"}.get(_m.get("signal", "fair"), "JUSTO")
                                _m_signals.append(_sig_label)

                        if _m_names:
                            _fig_mult = go.Figure()
                            _fig_mult.add_trace(go.Bar(
                                y=_m_names, x=_m_values,
                                orientation='h',
                                name="Valor Actual",
                                marker_color=_m_colors,
                                text=[f"{v:.2f}" for v in _m_values],
                                textposition="outside",
                                textfont=dict(color="#94a3b8", size=10),
                            ))
                            _fig_mult.add_trace(go.Scatter(
                                y=_m_names, x=_m_medians,
                                mode="markers",
                                name="Mediana Sector",
                                marker=dict(color="#a78bfa", size=10, symbol="diamond",
                                            line=dict(color="#f0f6ff", width=1)),
                            ))
                            _fig_mult.update_layout(
                                **dark_layout(
                                    height=max(350, len(_m_names) * 40),
                                    title=dict(text=f"Múltiplos de Valoración — {ticker_solo}",
                                               font=dict(color="#94a3b8", size=14), x=0.5),
                                    showlegend=True,
                                    legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a",
                                                font=dict(color="#94a3b8", size=10)),
                                    xaxis=dict(title="Valor", gridcolor="#1a1a1a"),
                                    yaxis=dict(autorange="reversed"),
                                    margin=dict(l=80, r=60, t=40, b=40),
                                ),
                            )
                            st.plotly_chart(_fig_mult, use_container_width=True)

                            # Signal summary badges
                            _sig_html = "<div style='display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:8px;'>"
                            for _mn, _mv, _ms, _mc in zip(_m_names, _m_values, _m_signals, _m_colors):
                                _sig_html += f"""<div style='background:#0a0a0a;border:1px solid {_mc};
                                    border-radius:8px;padding:6px 12px;text-align:center;'>
                                    <span style='color:#94a3b8;font-size:11px;'>{_mn}</span><br>
                                    <span style='color:{_mc};font-weight:700;font-size:12px;'>{_ms}</span></div>"""
                            _sig_html += "</div>"
                            st.markdown(_sig_html, unsafe_allow_html=True)
                        else:
                            st.info("No se pudieron calcular múltiplos para este ticker.")
                    else:
                        st.info("No hay datos de múltiplos disponibles.")
            except Exception as _e_b7:
                st.warning(f"Error calculando múltiplos: {_e_b7}")

        # ── B8: Capital Returns Cards ──
        with st.expander("💰 Retornos de Capital", expanded=False):
            try:
                if st.button("Calcular Retornos de Capital", key="btn_capital_returns"):
                    with st.spinner("Calculando retornos de capital…"):
                        _cap_ret = valuation.compute_capital_returns(ticker_solo)
                    if _cap_ret:
                        _roic_val = _cap_ret.get("roic")
                        _roce_val = _cap_ret.get("roce")
                        _sh_yield = _cap_ret.get("shareholder_yield")
                        _div_y = _cap_ret.get("div_yield", 0) or 0
                        _buyback_y = _cap_ret.get("buyback_yield", 0) or 0
                        _debt_pay_y = _cap_ret.get("debt_paydown_yield", 0) or 0

                        def _roic_color(v):
                            if v is None:
                                return "blue"
                            if v > 15:
                                return "green"
                            elif v > 10:
                                return "blue"
                            return "red"

                        _cr1, _cr2, _cr3 = st.columns(3)
                        _cr1.markdown(kpi("ROIC",
                            f"{_roic_val:.2f}%" if _roic_val is not None else "N/A",
                            "Retorno sobre Capital Invertido",
                            _roic_color(_roic_val)), unsafe_allow_html=True)
                        _cr2.markdown(kpi("ROCE",
                            f"{_roce_val:.2f}%" if _roce_val is not None else "N/A",
                            "Retorno sobre Capital Empleado",
                            _roic_color(_roce_val)), unsafe_allow_html=True)
                        _cr3.markdown(kpi("SHAREHOLDER YIELD",
                            f"{_sh_yield:.2f}%" if _sh_yield is not None else "N/A",
                            "Div + Buyback + Debt Paydown",
                            "green" if _sh_yield and _sh_yield > 3 else ("blue" if _sh_yield and _sh_yield > 0 else "red")),
                            unsafe_allow_html=True)

                        st.markdown("""<div style='font-size:11px;color:#5a6f8a;text-transform:uppercase;
                                    letter-spacing:1px;font-weight:600;margin:16px 0 8px;'>
                                    Desglose Shareholder Yield</div>""", unsafe_allow_html=True)
                        _br1, _br2, _br3 = st.columns(3)
                        _br1.markdown(kpi("DIVIDENDO", f"{_div_y:.2f}%",
                            "Rendimiento por dividendo", "green" if _div_y > 0 else "blue"),
                            unsafe_allow_html=True)
                        _br2.markdown(kpi("RECOMPRA", f"{_buyback_y:.2f}%",
                            "Buyback yield (cambio acciones)", "green" if _buyback_y > 0 else ("red" if _buyback_y < 0 else "blue")),
                            unsafe_allow_html=True)
                        _br3.markdown(kpi("PAGO DEUDA", f"{_debt_pay_y:.2f}%",
                            "Reduccion de deuda / Mkt Cap", "green" if _debt_pay_y > 0 else ("red" if _debt_pay_y < 0 else "blue")),
                            unsafe_allow_html=True)

                        _components = [
                            ("Dividendo", _div_y, "#34d399"),
                            ("Recompra", _buyback_y, "#60a5fa"),
                            ("Pago Deuda", _debt_pay_y, "#a78bfa"),
                        ]
                        _fig_cr = go.Figure()
                        for _comp_name, _comp_val, _comp_clr in _components:
                            _fig_cr.add_trace(go.Bar(
                                x=[_comp_name], y=[_comp_val],
                                marker_color=_comp_clr,
                                name=_comp_name,
                                text=[f"{_comp_val:.2f}%"],
                                textposition="outside",
                                textfont=dict(color="#94a3b8", size=11),
                            ))
                        _fig_cr.update_layout(
                            **dark_layout(
                                height=280,
                                title=dict(text="Componentes del Shareholder Yield",
                                           font=dict(color="#94a3b8", size=13), x=0.5),
                                showlegend=False,
                                yaxis=dict(title="%", gridcolor="#1a1a1a"),
                            ),
                        )
                        st.plotly_chart(_fig_cr, use_container_width=True)
                    else:
                        st.info("No se pudieron calcular retornos de capital.")
            except Exception as _e_b8:
                st.warning(f"Error calculando retornos de capital: {_e_b8}")

        # ── A1: Waterfall Income Statement ──
        with st.expander("📊 Waterfall — Estado de Resultados", expanded=False):
            try:
                if st.button("Generar Waterfall", key="btn_waterfall_income"):
                    with st.spinner("Obteniendo estado de resultados…"):
                        _tk_a1 = yf.Ticker(ticker_solo)
                        _inc_a1 = _tk_a1.income_stmt
                    if _inc_a1 is not None and not _inc_a1.empty:
                        def _get_a1(labels):
                            for _lbl in labels:
                                if _lbl in _inc_a1.index:
                                    _v = _inc_a1.loc[_lbl].iloc[0]
                                    if _v is not None and _v == _v:
                                        return float(_v)
                            return 0

                        _revenue = _get_a1(["Total Revenue", "Revenue"])
                        _cost_rev = _get_a1(["Cost Of Revenue", "Cost of Revenue"])
                        _gross_profit = _get_a1(["Gross Profit"])
                        if _gross_profit == 0 and _revenue and _cost_rev:
                            _gross_profit = _revenue - _cost_rev
                        _opex = _get_a1(["Operating Expense", "Total Operating Expenses", "Selling General And Administration"])
                        _ebit = _get_a1(["EBIT", "Operating Income"])
                        _interest = _get_a1(["Interest Expense", "Net Interest Income"])
                        _tax = _get_a1(["Tax Provision", "Income Tax Expense"])
                        _net_income = _get_a1(["Net Income", "Net Income Common Stockholders"])

                        def _fmt_abbr(v):
                            if abs(v) >= 1e9:
                                return f"${v/1e9:.1f}B"
                            elif abs(v) >= 1e6:
                                return f"${v/1e6:.1f}M"
                            elif abs(v) >= 1e3:
                                return f"${v/1e3:.1f}K"
                            return f"${v:.0f}"

                        _wf_labels = ["Revenue", "Cost of Revenue", "Gross Profit",
                                      "Operating Exp.", "EBIT", "Interest Exp.",
                                      "Tax Provision", "Net Income"]
                        _wf_measures = ["absolute", "relative", "total",
                                        "relative", "total", "relative",
                                        "relative", "total"]
                        _wf_values = [_revenue, -abs(_cost_rev), _gross_profit,
                                      -abs(_opex) if _opex else -(_gross_profit - _ebit),
                                      _ebit,
                                      -abs(_interest) if _interest else 0,
                                      -abs(_tax) if _tax else 0,
                                      _net_income]
                        _wf_text = [_fmt_abbr(v) for v in _wf_values]

                        _fig_wf = go.Figure(go.Waterfall(
                            name="Income Statement",
                            orientation="v",
                            measure=_wf_measures,
                            x=_wf_labels,
                            y=_wf_values,
                            text=_wf_text,
                            textposition="outside",
                            textfont=dict(color="#94a3b8", size=10),
                            increasing=dict(marker=dict(color="#34d399")),
                            decreasing=dict(marker=dict(color="#f87171")),
                            totals=dict(marker=dict(color="#3b82f6")),
                            connector=dict(line=dict(color="#1a1a1a", width=1)),
                        ))
                        _fig_wf.update_layout(
                            **dark_layout(
                                height=420,
                                title=dict(text=f"Waterfall — Estado de Resultados ({ticker_solo})",
                                           font=dict(color="#94a3b8", size=14), x=0.5),
                                showlegend=False,
                                yaxis=dict(title="USD", gridcolor="#1a1a1a"),
                                margin=dict(l=60, r=30, t=50, b=40),
                            ),
                        )
                        st.plotly_chart(_fig_wf, use_container_width=True)

                        _margin_net = (_net_income / _revenue * 100) if _revenue else 0
                        _margin_gross = (_gross_profit / _revenue * 100) if _revenue else 0
                        _margin_op = (_ebit / _revenue * 100) if _revenue else 0
                        _wm1, _wm2, _wm3 = st.columns(3)
                        _wm1.markdown(kpi("Margen Bruto", f"{_margin_gross:.1f}%", fmt(_gross_profit), "green"),
                                     unsafe_allow_html=True)
                        _wm2.markdown(kpi("Margen Operativo", f"{_margin_op:.1f}%", fmt(_ebit), "blue"),
                                     unsafe_allow_html=True)
                        _wm3.markdown(kpi("Margen Neto", f"{_margin_net:.1f}%", fmt(_net_income),
                                     "green" if _margin_net > 15 else ("yellow" if _margin_net > 5 else "red")),
                                     unsafe_allow_html=True)
                    else:
                        st.info("No se pudo obtener el estado de resultados para este ticker.")
            except Exception as _e_a1:
                st.warning(f"Error generando waterfall: {_e_a1}")

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
