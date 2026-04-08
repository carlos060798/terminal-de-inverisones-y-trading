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
# ── CSS LOADER ────────────────────────────────────────────────────────────────
def load_css(file_path):
    with open(file_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/styles.css")

# ── INIT ───────────────────────────────────────────────────────────────────────
db.init_db()

# ── BACKGROUND SYNC ────────────────────────────────────────────────────────────
from tasks.data_sync import init_scheduler

@st.cache_resource
def start_sync_tasks():
    """Lanza el scheduler de fondo una sola vez por sesión del servidor."""
    try:
        return init_scheduler()
    except Exception as e:
        st.warning(f"No se pudo iniciar el scheduler de fondo: {e}")
        return None

_scheduler = start_sync_tasks()

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
        # F3: Search History — track recent searches
        try:
            if "search_history" not in st.session_state:
                st.session_state.search_history = []
            _new_ticker = _ticker_in.strip().upper()
            if _new_ticker in st.session_state.search_history:
                st.session_state.search_history.remove(_new_ticker)
            st.session_state.search_history.insert(0, _new_ticker)
            st.session_state.search_history = st.session_state.search_history[:10]
        except Exception:
            pass

    # F3: Display search history as clickable buttons
    try:
        if st.session_state.get('search_history'):
            st.caption("Recientes:")
            cols = st.columns(min(len(st.session_state.search_history), 5))
            for i, t in enumerate(st.session_state.search_history[:5]):
                with cols[i]:
                    if st.button(t, key=f"hist_{t}"):
                        st.session_state.active_ticker = t
                        st.rerun()
    except Exception:
        pass

# ── ANT DESIGN NAVIGATION ─────────────────────────────────────────────────────
_active = sac.tabs([
    sac.TabsItem(label="Dashboard", icon="house"),
    sac.TabsItem(label="Acciones", icon="graph-up-arrow"),
    sac.TabsItem(label="Valor", icon="gem"),
    sac.TabsItem(label="Screener", icon="search"),
    sac.TabsItem(label="Tesis", icon="bullseye"),
    sac.TabsItem(label="Watchlist", icon="eye"),
    sac.TabsItem(label="Diario", icon="journal-text"),
    sac.TabsItem(label="Forex", icon="currency-exchange"),
    sac.TabsItem(label="Macro", icon="bar-chart-line"),
    sac.TabsItem(label="Backtest", icon="graph-down"),
    sac.TabsItem(label="Comparador", icon="arrows-angle-expand"),
    sac.TabsItem(label="Alertas", icon="bell"),
    sac.TabsItem(label="Plan Trading", icon="clipboard-data"),
    sac.TabsItem(label="Fractales", icon="search"),
    sac.TabsItem(label="Data Health", icon="activity"),
    sac.TabsItem(label="Sistema", icon="gear"),
], color="blue", size="sm", return_index=False)

# ── ROUTING ────────────────────────────────────────────────────────────────────
_routes = {
    "Dashboard": "sections.dashboard",
    "Acciones": "sections.stock_analyzer",
    "Valor": "sections.value_center",
    "Screener": "sections.screener",
    "Tesis": "sections.investment_thesis",
    "Watchlist": "sections.watchlist",
    "Diario": "sections.trading_journal",
    "Forex": "sections.forex_trading",
    "Macro": "sections.macro_context",
    "Backtest": "sections.backtest",
    "Comparador": "sections.comparator",
    "Alertas": "sections.alerts",
    "Plan Trading": "sections.trading_plan",
    "Fractales": "sections.pattern_matcher",
    "Data Health": "sections.data_health",
    "Sistema": "sections.system_health",
}
if _active in _routes:
    _mod = __import__(_routes[_active], fromlist=["render"])
    _mod.render()
