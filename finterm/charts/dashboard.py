"""
finterm/charts/dashboard.py
Streamlit orchestrator for the finterm visualization system.
"""
import streamlit as st
import pandas as pd
import yfinance as yf
from finterm import charts as fc

def render_dashboard(ticker="AAPL"):
    st.set_page_config(page_title=f"Quantum Terminal - {ticker}", layout="wide")
    
    # Custom CSS for UI polish
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {fc.COLORS['bg_main']}; color: {fc.COLORS['text_main']}; }}
    [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
    .kpi-card {{
        background: {fc.COLORS['bg_panel']};
        border: 1px solid {fc.COLORS['grid']};
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }}
    </style>
    """, unsafe_allow_html=True)

    # ── HEADER ──
    try:
        data = yf.Ticker(ticker)
        info = data.info
        price = info.get("regularMarketPrice", info.get("currentPrice", 0))
        change = info.get("regularMarketChangePercent", 0)
    except:
        st.error("Error al cargar datos de yfinance.")
        return

    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(f"<h1>{info.get('longName', ticker)} <span style='color:{fc.COLORS['text_sec']};font-size:20px;'>({ticker})</span></h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:{fc.COLORS['text_sec']}'>{info.get('sector', '--')} · {info.get('industry', '--')} · {info.get('exchange', '--')}</p>", unsafe_allow_html=True)
    
    with c2:
        color = fc.COLORS["bull"] if change >= 0 else fc.COLORS["bear"]
        st.markdown(f"""
        <div style='text-align:right'>
            <div style='font-size:32px;font-weight:800'>${price:.2f}</div>
            <div style='color:{color};font-weight:700'>{change:+.2f}% TODAY</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── SIDEBAR: SCORE & RADAR ──
    with st.sidebar:
        st.image("https://raw.githubusercontent.com/carlos060798/terminal-de-inverisones-y-trading/main/assets/logo.png", width=200)
        st.markdown("### Quantum Score")
        
        # Mock score for demo
        mock_score = 72
        mock_breakdown = {
            "Fundamental": 85,
            "Technical": 60,
            "Sentiment": 90,
            "Risk": 40,
            "Institutional": 55
        }
        
        st.plotly_chart(fc.create_score_gauge(mock_score), use_container_width=True)
        st.plotly_chart(fc.create_component_radar(mock_breakdown, ticker), use_container_width=True)
        
        if st.button("Exportar Reporte PDF", use_container_width=True):
            st.toast("Generando reporte...")

    # ── MAIN TABS ──
    t_tech, t_fund, t_sent, t_port = st.tabs(["📈 TÉCNICO", "🏛️ FUNDAMENTAL", "🧠 SENTIMIENTO IA", "💼 PORTAFOLIO"])

    with t_tech:
        hist = data.history(period="1y")
        # Add basic indicators for visual display
        hist['MA20'] = hist['Close'].rolling(20).mean()
        hist['MA50'] = hist['Close'].rolling(50).mean()
        hist['RSI'] = 50 + (hist['Close'].pct_change().rolling(14).mean() * 1000) # Mock RSI
        hist['MACD'] = hist['Close'].rolling(12).mean() - hist['Close'].rolling(26).mean()
        hist['Signal'] = hist['MACD'].rolling(9).mean()
        hist['Hist'] = hist['MACD'] - hist['Signal']
        
        st.plotly_chart(fc.create_technical_dashboard(hist, ticker), use_container_width=True)

    with t_fund:
        f1, f2 = st.columns(2)
        with f1:
            # Mock historical data
            df_hist = pd.DataFrame({
                "Year": [2020, 2021, 2022, 2023, 2024],
                "Revenue": [274e9, 365e9, 394e9, 383e9, 400e9],
                "Net Income": [57e9, 94e9, 99e9, 96e9, 105e9]
            })
            st.plotly_chart(fc.create_revenue_earnings_chart(df_hist), use_container_width=True)
        with f2:
            st.markdown("#### Métricas Clave")
            m1, m2 = st.columns(2)
            m1.metric("P/E Ratio", f"{info.get('trailingPE', 0):.2f}")
            m2.metric("Market Cap", f"${info.get('marketCap', 0)/1e12:.2f}T")

    with t_sent:
        s1, s2 = st.columns([2, 1])
        with s1:
            # Mock news data
            df_news = pd.DataFrame({
                "date": pd.date_range(start="2024-01-01", periods=10, freq='D'),
                "sentiment_score": [0.5, -0.2, 0.8, 0.1, -0.5, 0.4, 0.9, 0.0, 0.3, -0.1],
                "title": [f"Noticia {i}" for i in range(10)]
            })
            st.plotly_chart(fc.create_sentiment_timeline(df_news), use_container_width=True)
        with s2:
            st.plotly_chart(fc.create_sentiment_donut(60, 20, 20), use_container_width=True)

    with t_port:
        # Correlation Matrix Mock
        corr_data = pd.DataFrame(
            [[1, 0.8, 0.3], [0.8, 1, 0.4], [0.3, 0.4, 1]], 
            columns=[ticker, "SPY", "QQQ"], 
            index=[ticker, "SPY", "QQQ"]
        )
        st.plotly_chart(fc.create_allocation_donut({ticker: 0.4, "MSFT": 0.3, "NVDA": 0.3}), use_container_width=True)
        st.plotly_chart(fc.create_correlation_heatmap(corr_data), use_container_width=True)

if __name__ == "__main__":
    import sys
    tick = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    render_dashboard(tick)
