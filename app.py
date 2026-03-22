"""
Quantum Retail Terminal — Pro Edition
Dashboard privado de inversiones · Streamlit + SQLite + yfinance
"""
import streamlit as st
import streamlit.components.v1 as components
import streamlit_antd_components as sac
import database as db

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Quantum Retail Terminal",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── PROFESSIONAL DARK CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

* { font-family: 'Inter', sans-serif !important; }

/* Material Symbols — removed; handled via stIconMaterial selectors below */

/* ══════════════════════════════════════════════════════════════
   BASE & GLOBAL
   ══════════════════════════════════════════════════════════════ */
.stApp {
    background: #000000;
    color: #e2e8f0;
}
/* Remove top padding — full-width panels */
.main .block-container {
    padding-top: 0.5rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}
/* Clean iframes for TradingView widgets */
iframe {
    border: none !important;
    overflow: hidden !important;
}
[data-testid="stIFrame"] {
    border: none !important;
    border-radius: 0 !important;
}

/* Hide Streamlit header bar & footer */
header[data-testid="stHeader"] { background: transparent !important; }
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
.stDeployButton { display: none !important; }

/* ══════════════════════════════════════════════════════════════
   SIDEBAR — hidden (menu moved to top)
   ══════════════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] { display: none !important; }
button[data-testid="stBaseButton-headerNoPadding"],
button[data-testid="stExpandSidebarButton"] { display: none !important; }

/* Hide material icon text in expander arrows */
[data-testid="stExpander"] [data-testid="stIconMaterial"] {
    font-size: 0 !important;
    display: inline-flex !important;
    align-items: center !important;
    width: 18px !important;
    height: 18px !important;
}
[data-testid="stExpander"] [data-testid="stIconMaterial"]::before {
    content: '▸';
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    color: #5a6f8a !important;
}
[data-testid="stExpander"][open] [data-testid="stIconMaterial"]::before {
    content: '▾';
}

/* TOP NAV BAR — handled by Streamlit buttons above */

/* ══════════════════════════════════════════════════════════════
   TOP HEADER BANNER
   ══════════════════════════════════════════════════════════════ */
.top-header {
    background: #000000;
    border: 1px solid #111111;
    border-radius: 20px;
    padding: 28px 36px;
    margin-bottom: 32px;
    position: relative;
    overflow: hidden;
}
.top-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
}
.top-header h1 {
    font-size: 28px !important;
    font-weight: 800 !important;
    color: #f0f6ff !important;
    margin: 0 !important;
    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #c084fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px !important;
}
.top-header p {
    color: #64748b !important;
    font-size: 13px;
    margin: 6px 0 0 0;
    letter-spacing: 0.3px;
}

/* ══════════════════════════════════════════════════════════════
   KPI CARDS
   ══════════════════════════════════════════════════════════════ */
.kpi-card {
    background: linear-gradient(145deg, #0a0a0a, #111111);
    border: 1px solid #1a1a1a;
    border-radius: 16px;
    padding: 22px 24px;
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
}
.kpi-card:hover {
    border-color: rgba(59,130,246,0.3);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    opacity: 0.8;
}
.kpi-label {
    font-size: 10px; font-weight: 600; color: #5a6f8a;
    text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 10px;
}
.kpi-value { font-size: 26px; font-weight: 800; color: #f0f6ff; line-height: 1.1; }
.kpi-sub   { font-size: 12px; margin-top: 8px; font-weight: 500; }
.kpi-green { color: #34d399; }
.kpi-red   { color: #f87171; }
.kpi-blue  { color: #60a5fa; }
.kpi-purple{ color: #a78bfa; }

/* ══════════════════════════════════════════════════════════════
   SECTION TITLES
   ══════════════════════════════════════════════════════════════ */
.sec-title {
    font-size: 13px; font-weight: 700; color: #7b8faa;
    text-transform: uppercase; letter-spacing: 1.5px;
    border-left: 3px solid #3b82f6;
    padding-left: 14px; margin: 32px 0 18px 0;
}

/* ══════════════════════════════════════════════════════════════
   SCORE BADGE
   ══════════════════════════════════════════════════════════════ */
.score-ring {
    background: #0a0a0a;
    border: 1px solid #1a1a1a;
    border-radius: 16px;
    padding: 20px;
    text-align: center;
}

/* ══════════════════════════════════════════════════════════════
   METRIC CARDS
   ══════════════════════════════════════════════════════════════ */
.metric-card {
    background: #0a0a0a;
    border: 1px solid #1a1a1a;
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 10px;
    transition: all 0.2s ease;
}
.metric-card:hover { border-color: rgba(59,130,246,0.2); }
.metric-card .mc-label { font-size: 10px; color: #5a6f8a; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }
.metric-card .mc-value { font-size: 24px; font-weight: 800; color: #f0f6ff; margin: 8px 0 6px; }
.metric-card .mc-bench { font-size: 11px; color: #475569; }
.metric-pass { border-left: 3px solid #34d399; }
.metric-fail { border-left: 3px solid #f87171; }
.metric-na   { border-left: 3px solid #475569; }

/* ══════════════════════════════════════════════════════════════
   TABLES (DataFrames)
   ══════════════════════════════════════════════════════════════ */
[data-testid="stDataFrame"] {
    border-radius: 14px; overflow: hidden;
    border: 1px solid #1a1a1a !important;
}
thead tr th {
    background: #0a0a0a !important; color: #5a6f8a !important; font-size: 10px !important;
    text-transform: uppercase !important; letter-spacing: 1px !important;
    font-weight: 700 !important; padding: 12px 16px !important;
}
tbody tr td {
    background: #050505 !important; color: #e2e8f0 !important; font-size: 13px !important;
    border-color: #1a1a1a !important; padding: 10px 16px !important;
}
tbody tr:hover td { background: #111111 !important; }

/* ══════════════════════════════════════════════════════════════
   ALL INPUTS (text, number, textarea, select, date)
   ══════════════════════════════════════════════════════════════ */
/* Input wrapper containers — override Streamlit light backgrounds */
.stTextInput > div, .stTextInput > div > div,
.stNumberInput > div, .stNumberInput > div > div, .stNumberInput > div > div > div,
.stTextArea > div, .stTextArea > div > div,
.stDateInput > div > div,
[data-testid="stTextInput"] > div, [data-testid="stTextInput"] > div > div,
[data-testid="stNumberInput"] > div > div, [data-testid="stNumberInput"] > div > div > div,
[data-testid="stTextArea"] > div, [data-testid="stTextArea"] > div > div {
    background-color: transparent !important;
    background: transparent !important;
}
.stTextInput input, .stNumberInput input, .stTextArea textarea,
.stDateInput input {
    background: #0a0a0a !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-size: 13px !important;
    transition: all 0.2s ease !important;
}
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
    border-color: rgba(59,130,246,0.6) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
}
/* Selectbox */
.stSelectbox > div,
.stSelectbox > div > div,
[data-baseweb="select"],
[data-baseweb="select"] > div {
    background: #0a0a0a !important;
    border-color: #1a1a1a !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
}
.stSelectbox > div > div,
[data-baseweb="select"] > div {
    border: 1px solid #1a1a1a !important;
}
/* Selectbox dropdown menu */
[data-baseweb="popover"] > div,
[data-baseweb="menu"] {
    background: #0a0a0a !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 10px !important;
}
[data-baseweb="menu"] li {
    color: #c8d6e5 !important;
    background: transparent !important;
}
[data-baseweb="menu"] li:hover {
    background: rgba(59,130,246,0.12) !important;
}
/* Number input stepper buttons */
.stNumberInput button,
[data-testid="stNumberInput"] button {
    background: #111111 !important;
    border: 1px solid #1a1a1a !important;
    color: #94a3b8 !important;
    border-radius: 6px !important;
}
.stNumberInput button:hover,
[data-testid="stNumberInput"] button:hover {
    background: rgba(59,130,246,0.2) !important;
    border-color: rgba(59,130,246,0.4) !important;
    color: #e2e8f0 !important;
}
/* Number input container */
[data-testid="stNumberInput"] > div {
    border-radius: 10px !important;
}
/* Date input */
[data-testid="stDateInput"] > div > div {
    background: #0a0a0a !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 10px !important;
}
/* Slider */
.stSlider > div > div > div {
    color: #94a3b8 !important;
}
/* Labels */
.stTextInput label, .stNumberInput label, .stTextArea label,
.stSelectbox label, .stDateInput label, .stSlider label,
.stFileUploader label, .stRadio label, .stCheckbox label {
    color: #7b8faa !important;
    font-size: 12px !important;
    font-weight: 500 !important;
}

/* ══════════════════════════════════════════════════════════════
   FILE UPLOADER
   ══════════════════════════════════════════════════════════════ */
[data-testid="stFileUploader"] {
    background: transparent !important;
}
[data-testid="stFileUploader"] > div {
    background: transparent !important;
}
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploader"] section {
    background: #0a0a0a !important;
    border: 2px dashed rgba(59,130,246,0.25) !important;
    border-radius: 14px !important;
    padding: 32px 20px !important;
    transition: all 0.3s ease !important;
}
[data-testid="stFileUploaderDropzone"]:hover,
[data-testid="stFileUploader"] section:hover {
    border-color: rgba(59,130,246,0.5) !important;
    background: rgba(59,130,246,0.04) !important;
}
[data-testid="stFileUploaderDropzone"] *,
[data-testid="stFileUploader"] section * {
    color: #7b8faa !important;
}
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploader"] section button {
    background: rgba(59,130,246,0.15) !important;
    border: 1px solid rgba(59,130,246,0.3) !important;
    color: #60a5fa !important;
    border-radius: 8px !important;
}
/* Small file uploader text */
[data-testid="stFileUploader"] small {
    color: #475569 !important;
}

/* ══════════════════════════════════════════════════════════════
   BUTTONS
   ══════════════════════════════════════════════════════════════ */
.stButton > button {
    background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    font-size: 13px !important; padding: 10px 24px !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 16px rgba(37,99,235,0.2) !important;
    letter-spacing: 0.3px !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(37,99,235,0.35) !important;
}
.stButton > button:active {
    transform: translateY(0px) !important;
}
/* Download button */
.stDownloadButton > button {
    background: linear-gradient(135deg, #059669 0%, #10b981 100%) !important;
    box-shadow: 0 4px 16px rgba(5,150,105,0.2) !important;
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #10b981 0%, #34d399 100%) !important;
    box-shadow: 0 8px 24px rgba(5,150,105,0.35) !important;
}

/* ══════════════════════════════════════════════════════════════
   EXPANDERS
   ══════════════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
    border: 1px solid #1a1a1a !important;
    border-radius: 14px !important;
    overflow: hidden;
    background: transparent !important;
}
[data-testid="stExpander"] summary,
.streamlit-expanderHeader {
    background: #0a0a0a !important;
    border: none !important;
    border-radius: 0 !important;
    color: #94a3b8 !important;
    font-weight: 500 !important;
    padding: 14px 20px !important;
}
[data-testid="stExpander"] summary:hover,
.streamlit-expanderHeader:hover {
    background: #111111 !important;
}
[data-testid="stExpander"] > div:last-child,
.streamlit-expanderContent {
    background: #050505 !important;
    border: none !important;
    border-top: 1px solid #1a1a1a !important;
    padding: 16px 20px !important;
}
/* Fix expander arrow icon */
[data-testid="stExpander"] summary svg {
    color: #5a6f8a !important;
}

/* ══════════════════════════════════════════════════════════════
   TABS
   ══════════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    background: #0a0a0a !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid #1a1a1a !important;
}
.stTabs [data-baseweb="tab"] {
    color: #5a6f8a !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    background: transparent !important;
    border: none !important;
    transition: all 0.2s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #94a3b8 !important;
    background: rgba(59,130,246,0.06) !important;
}
.stTabs [aria-selected="true"] {
    color: #60a5fa !important;
    background: rgba(59,130,246,0.12) !important;
    font-weight: 600 !important;
}
/* Tab highlight bar */
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #3b82f6 !important;
    border-radius: 2px !important;
}
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}

/* ══════════════════════════════════════════════════════════════
   ALERTS (info, success, warning, error)
   ══════════════════════════════════════════════════════════════ */
.stAlert, [data-testid="stAlert"] {
    border-radius: 12px !important;
    border: none !important;
    backdrop-filter: blur(8px) !important;
}
div[data-testid="stAlert"][data-baseweb="notification"] {
    border-radius: 12px !important;
}
/* Info */
.stAlert > div[role="alert"]:has(.st-emotion-cache-info),
div[data-baseweb="notification"][kind="info"] {
    background: rgba(59,130,246,0.08) !important;
    border-left: 3px solid #3b82f6 !important;
    color: #93c5fd !important;
}
/* Success */
div[data-baseweb="notification"][kind="positive"] {
    background: rgba(34,197,94,0.08) !important;
    border-left: 3px solid #22c55e !important;
    color: #86efac !important;
}
/* Warning */
div[data-baseweb="notification"][kind="warning"] {
    background: rgba(234,179,8,0.08) !important;
    border-left: 3px solid #eab308 !important;
    color: #fde047 !important;
}

/* ══════════════════════════════════════════════════════════════
   SPINNER
   ══════════════════════════════════════════════════════════════ */
[data-testid="stSpinner"] > div {
    color: #60a5fa !important;
}

/* ══════════════════════════════════════════════════════════════
   DIVIDERS & SCROLLBAR
   ══════════════════════════════════════════════════════════════ */
hr { border-color: #1a1a1a !important; margin: 28px 0 !important; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1a1a1a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(59,130,246,0.4); }

/* ══════════════════════════════════════════════════════════════
   PLOTLY CHARTS CONTAINER
   ══════════════════════════════════════════════════════════════ */
[data-testid="stPlotlyChart"] {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid #1a1a1a;
}

/* ══════════════════════════════════════════════════════════════
   CAPTION / SMALL TEXT
   ══════════════════════════════════════════════════════════════ */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #5a6f8a !important;
}

/* ══════════════════════════════════════════════════════════════
   MARKDOWN TEXT
   ══════════════════════════════════════════════════════════════ */
.stMarkdown h4 {
    color: #c8d6e5 !important;
}
.stMarkdown p, .stMarkdown li {
    color: #94a3b8 !important;
}

/* ══════════════════════════════════════════════════════════════
   GLOBAL ANIMATIONS
   ══════════════════════════════════════════════════════════════ */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
.top-header, .kpi-card, .metric-card, [data-testid="stExpander"] {
    animation: fadeIn 0.4s ease-out;
}
</style>
""", unsafe_allow_html=True)

# ── INIT ───────────────────────────────────────────────────────────────────────
db.init_db()

# ── GLOBAL STATE ──────────────────────────────────────────────────────────────
for _key, _default in [("active_ticker", ""), ("last_section", ""), ("nav_history", [])]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ── TICKER TAPE (Top Ribbon — precios en vivo) ───────────────────────────────
components.html("""
<div class="tradingview-widget-container">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
    {
      "symbols": [
        {"proName":"FOREXCOM:SPXUSD","title":"S&P 500"},
        {"proName":"FOREXCOM:NSXUSD","title":"US 100"},
        {"proName":"FX_IDC:EURUSD","title":"EUR/USD"},
        {"proName":"BITSTAMP:BTCUSD","title":"Bitcoin"},
        {"proName":"BITSTAMP:ETHUSD","title":"Ethereum"},
        {"proName":"FOREXCOM:DJI","title":"Dow Jones"},
        {"proName":"TVC:GOLD","title":"Gold"},
        {"proName":"TVC:US10Y","title":"US 10Y"}
      ],
      "showSymbolLogo": true,
      "isTransparent": true,
      "displayMode": "adaptive",
      "colorTheme": "dark",
      "locale": "es"
    }
  </script>
</div>
""", height=46)


# Header row: brand + search
_hdr1, _hdr2 = st.columns([5, 1])
with _hdr1:
    st.markdown("<span style='font-size:17px;font-weight:800;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.5px;'>💎 Quantum Retail Terminal</span><span style='font-size:10px;color:#3e5068;margin-left:10px;text-transform:uppercase;letter-spacing:1.5px;'>Pro Edition · v5.1</span>", unsafe_allow_html=True)
with _hdr2:
    _ticker_in = st.text_input("🔍", placeholder="Ticker (ej: AAPL)",
                                value=st.session_state.get("active_ticker", ""),
                                label_visibility="collapsed")
    if _ticker_in.strip() and _ticker_in.strip().upper() != st.session_state.get("active_ticker", ""):
        st.session_state.active_ticker = _ticker_in.strip().upper()

# ── ANT DESIGN NAVIGATION ─────────────────────────────────────────────────────
_active = sac.tabs([
    sac.TabsItem(label="Dashboard", icon="house"),
    sac.TabsItem(label="Acciones", icon="graph-up-arrow"),
    sac.TabsItem(label="Screener", icon="search"),
    sac.TabsItem(label="Tesis", icon="bullseye"),
    sac.TabsItem(label="Watchlist", icon="eye"),
    sac.TabsItem(label="Diario", icon="journal-text"),
    sac.TabsItem(label="Forex", icon="currency-exchange"),
    sac.TabsItem(label="Macro", icon="bar-chart-line"),
    sac.TabsItem(label="Backtest", icon="graph-down"),
    sac.TabsItem(label="Comparador", icon="arrows-angle-expand"),
    sac.TabsItem(label="Alertas", icon="bell"),
    sac.TabsItem(label="Sistema", icon="gear"),
], color="blue", size="sm", return_index=False)

# ── ROUTING ────────────────────────────────────────────────────────────────────
_routes = {
    "Dashboard": "sections.dashboard",
    "Acciones": "sections.stock_analyzer",
    "Screener": "sections.screener",
    "Tesis": "sections.investment_thesis",
    "Watchlist": "sections.watchlist",
    "Diario": "sections.trading_journal",
    "Forex": "sections.forex_trading",
    "Macro": "sections.macro_context",
    "Backtest": "sections.backtest",
    "Comparador": "sections.comparator",
    "Alertas": "sections.alerts",
    "Sistema": "sections.system_health",
}
if _active in _routes:
    _mod = __import__(_routes[_active], fromlist=["render"])
    _mod.render()
