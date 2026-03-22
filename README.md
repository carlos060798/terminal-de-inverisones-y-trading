---
title: Quantum Retail Terminal
emoji: "\U0001F48E"
colorFrom: blue
colorTo: purple
sdk: docker
app_file: app.py
pinned: false
---

# Quantum Retail Terminal — Pro Edition

Terminal institucional de inversiones para retail — Streamlit + SQLite + yfinance. 100% gratis.

## Secciones

| Sección | Funcionalidades |
|---|---|
| Dashboard | KPIs de cartera, P&L, Sharpe, Sortino, VaR, Drawdown |
| Acciones | PDF parser, Fair Value, Health Scores, TradingView charts, AI analysis |
| Screener | Filtros fundamentales, Sector Heatmap, Multi-Factor Quant Score |
| Tesis | MOAT analysis, Porter 5 Forces, Bull/Bear thesis |
| Watchlist | Cartera en tiempo real, Correlación, Monte Carlo, Efficient Frontier |
| Diario | Trading journal con psicología, win rate, equity curve |
| Forex | Multi-instrumento: FX, Indices, Commodities, Crypto |
| Macro | Yield curve, FRED data, economic indicators |
| Backtest | SMA Crossover, RSI strategies con equity curves |
| Sistema | API health, DB stats, diagnostics |

## Stack
- **Frontend**: Streamlit + TradingView widgets + Plotly + Ant Design
- **Data**: yfinance, FRED API, Finviz
- **AI**: Gemini + Groq + OpenRouter (fallback chain)
- **DB**: SQLite (persistent)
- **Export**: Excel (openpyxl) + PDF (fpdf2)

## Local Setup
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment
See [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md) for full deployment instructions covering Streamlit Cloud, Hugging Face Spaces, Oracle Cloud, and Hetzner VPS.
