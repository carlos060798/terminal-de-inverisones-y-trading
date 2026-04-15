"""
Quantum Retail Terminal — Pro Edition
Dashboard privado de inversiones · Streamlit + SQLite + yfinance
"""
import streamlit as st
from datetime import datetime
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


# ── GLOBAL STATE ──────────────────────────────────────────────────────────────
if "cache_cleared_once" not in st.session_state:
    st.cache_resource.clear()
    st.session_state["cache_cleared_once"] = True

for _key, _default in [
    ("active_ticker", ""), 
    ("last_section", ""), 
    ("nav_history", []), 
    ("force_llm", "Auto-Balanceador"), 
    ("active_workspace", "Standard"), 
    ("active_portfolio_id", 1),
    ("notation_mode", "Compacto (M/B)"), # Compacto vs Normal
    ("vibrant_design", True)
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ── SIDEBAR SETTINGS ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧠 Inteligencia Artificial")
    _models = [
        "Auto-Balanceador",
        "groq-llama", 
        "deepseek-reasoner",
        "deepseek-chat",
        "openai-4o",
        "openai-4o-mini",
        "gemini-2.5-flash-preview-04-17",
        "or-qwen",
        "or-deepseek"
    ]
    _display_names = {
        "Auto-Balanceador": "Auto-Balanceador (Recomendado)",
        "groq-llama": "Llama 3.3 70B (Groq) — Rápido",
        "deepseek-reasoner": "DeepSeek R1 — Razonamiento",
        "deepseek-chat": "DeepSeek V3 — Chat",
        "openai-4o": "GPT-4o — Calidad",
        "openai-4o-mini": "GPT-4o Mini — Rápido",
        "gemini-2.5-flash-preview-04-17": "Gemini 2.5 Flash",
        "or-qwen": "Qwen 72B Free",
        "or-deepseek": "DeepSeek R1 Free"
    }
    
    current_idx = 0
    if st.session_state.force_llm in _models:
        current_idx = _models.index(st.session_state.force_llm)
        
    selected_name = st.selectbox(
        "Forzar Modelo (Global)",
        options=[_display_names[m] for m in _models],
        index=current_idx,
        help="Si eliges un modelo manual, todas las herramientas del terminal intentarán usarlo primero."
    )
    
    for m, name in _display_names.items():
        if name == selected_name:
            st.session_state.force_llm = m
            break
            
    st.markdown("---")

def clean_session_memory(leaving_section=None):
    """Purge heavy objects from the specific leaving section to maintain fluidity."""
    map_purge = {
        "Macro": ["macro_data", "liq_data", "cmv_data"],
        "Acciones": ["technical_cache", "partial_v"],
        "Screener": ["screener_results", "screener_cache"],
        "Forex": ["forex_history_cache"]
    }
    
    # Generic purge for keys often found in session but not needed across boundaries
    generic_to_purge = ["temp_render_cache"]
    for p_key in generic_to_purge:
        if p_key in st.session_state: del st.session_state[p_key]
        
    if leaving_section in map_purge:
        for p_key in map_purge[leaving_section]:
            if p_key in st.session_state:
                del st.session_state[p_key]

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
        {"coolName":"FX_IDC:EURUSD","title":"EUR/USD"},
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


# ── TOP STICKY HEADER ─────────────────────────────────────────────────────────
st.markdown('<div class="top-header">', unsafe_allow_html=True)
_hdr1, _hdr_port, _hdr2, _hdr3 = st.columns([2.5, 1.5, 1.2, 1])
with _hdr1:
    st.markdown("<span style='font-size:17px;font-weight:800;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.5px;'>💎 Quantum Terminal</span><span style='font-size:10px;color:#3e5068;margin-left:10px;text-transform:uppercase;letter-spacing:1.5px;'>v7.1</span>", unsafe_allow_html=True)

with _hdr_port:
    # --- PORTFOLIO SWITCHER ---
    db.init_db() # Ensure tables exist
    p_df = db.get_portfolios()
    if p_df.empty:
        p_list = ["Principal"]
        p_map = {"Principal": 1}
    else:
        p_list = p_df["name"].tolist()
        p_map = dict(zip(p_df["name"], p_df["id"]))
    
    curr_p_id = st.session_state.active_portfolio_id
    curr_p_name = next((name for name, p_id in p_map.items() if p_id == curr_p_id), "Principal")
    
    new_p_name = st.selectbox("Portfolio", options=p_list,
                                index=p_list.index(curr_p_name) if curr_p_name in p_list else 0,
                                label_visibility="collapsed", key="global_portfolio_selector")
    if p_map.get(new_p_name) != curr_p_id:
        st.session_state.active_portfolio_id = p_map.get(new_p_name, 1)
        st.rerun()

with _hdr2:
    w_df = db.get_workspaces()
    w_list = w_df["name"].tolist() if not w_df.empty else ["Standard"]
    curr_w = st.session_state.active_workspace
    new_w = st.selectbox("Workspace", options=w_list, 
                            index=w_list.index(curr_w) if curr_w in w_list else 0,
                            label_visibility="collapsed", key="global_workspace_selector")
    if new_w != curr_w:
        st.session_state.active_workspace = new_w
        import json
        config = w_df[w_df["name"] == new_w]["config_json"].iloc[0]
        st.session_state["w_config"] = json.loads(config)
        st.rerun()

with _hdr3:
    _ticker_in = st.text_input("🔍", placeholder="Ticker",
                                value=st.session_state.get("active_ticker", ""),
                                label_visibility="collapsed")
    if _ticker_in.strip() and _ticker_in.strip().upper() != st.session_state.get("active_ticker", ""):
        st.session_state.active_ticker = _ticker_in.strip().upper()
        # Search History logic
        try:
            if "search_history" not in st.session_state:
                st.session_state.search_history = []
            _new_ticker = _ticker_in.strip().upper()
            if _new_ticker in st.session_state.search_history:
                st.session_state.search_history.remove(_new_ticker)
            st.session_state.search_history.insert(0, _new_ticker)
            st.session_state.search_history = st.session_state.search_history[:10]
        except Exception: pass
st.markdown('</div>', unsafe_allow_html=True)

# ── SEARCH HISTORY BUTTONS (Just below header) ──────────────────────────────
if st.session_state.get('search_history'):
    cols = st.columns(min(len(st.session_state.search_history), 8))
    for i, t in enumerate(st.session_state.search_history[:8]):
        with cols[i]:
            if st.button(t, key=f"hist_{t}", use_container_width=True):
                st.session_state.active_ticker = t
                st.rerun()

# ── ANT DESIGN NAVIGATION ─────────────────────────────────────────────────────
# ── INIT & BACKUP ──────────────────────────────────────────────────────────────
db.init_db()

@st.cache_resource
def perform_startup_backup():
    try:
        from services import backup_service
        backup_service.run_backup(db.DB_PATH)
    except Exception: pass

perform_startup_backup()

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

_active = sac.tabs([
    sac.TabsItem(label="Dashboard", icon="house"),
    sac.TabsItem(label="Quantum AI", icon="robot"),
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
    sac.TabsItem(label="Centro Técnico", icon="gear"),
], color="blue", size="sm", return_index=False)

# ── ROUTING ────────────────────────────────────────────────────────────────────
_routes = {
    "Dashboard": "sections.dashboard",
    "Quantum AI": "sections.quantum_ai",
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
    "Centro Técnico": "sections.system_health",
}
if _active in _routes:
    # Dismount logic: selective purge if we changed section
    if st.session_state.last_section != _active:
        clean_session_memory(leaving_section=st.session_state.last_section)
        st.session_state.last_section = _active

    _mod = __import__(_routes[_active], fromlist=["render"])
    # ── SIDEBAR SETTINGS ────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Preferencias")
        with st.expander("🎨 Interfaz & Datos"):
            st.session_state.notation_mode = st.selectbox(
                "Notación Financiera", 
                ["Compacto (M/B)", "Cifras Completas"],
                index=0 if st.session_state.notation_mode == "Compacto (M/B)" else 1
            )
            st.session_state.vibrant_design = st.toggle("Habilitar Diseño Vibrante", value=st.session_state.vibrant_design)
            
        st.markdown("---")
        st.caption("Quantum Retail Terminal v8.9.2")

    _mod.render()
