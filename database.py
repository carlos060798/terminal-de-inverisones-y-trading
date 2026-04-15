import sqlite3
import json
import pandas as pd
import yfinance as yf
import os
from models import init_models, SessionLocal, engine

# Use /tmp for writable DB in containerized environments (HF Spaces, Docker)
_app_dir = os.path.dirname(__file__)
_db_in_app = os.path.join(_app_dir, "investment_data.db")
if os.path.isfile(_db_in_app) and os.access(_app_dir, os.W_OK):
    DB_PATH = _db_in_app
elif os.access(_app_dir, os.W_OK):
    DB_PATH = _db_in_app
else:
    DB_PATH = os.path.join("/tmp", "investment_data.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn

def get_session():
    """Returns a new SQLAlchemy database session."""
    return SessionLocal()

def init_db():
    """Create all tables if they don't exist (using SQLAlchemy and raw SQL migrations)."""
    # Create tables via SQLAlchemy metadata
    init_models()
    
    # Optional: Keep raw migrations for legacy fields if needed
    conn = get_connection()
    c = conn.cursor()
    
    # Migrations for existing DB if using raw SQL
    try:
        c.execute("ALTER TABLE watchlist ADD COLUMN notes TEXT DEFAULT ''")
    except: pass
    try:
        c.execute("ALTER TABLE watchlist ADD COLUMN industry TEXT DEFAULT ''")
    except: pass
    try:
        c.execute("ALTER TABLE watchlist ADD COLUMN target_weight REAL DEFAULT 0.0")
    except: pass
    try:
        c.execute("ALTER TABLE price_alerts ADD COLUMN alert_type TEXT DEFAULT 'fixed'")
    except: pass
    try:
        c.execute("ALTER TABLE price_alerts ADD COLUMN multiplier REAL DEFAULT 0.0")
    except: pass
    try:
        c.execute("ALTER TABLE watchlist ADD COLUMN stop_loss REAL")
    except: pass
    try:
        c.execute("ALTER TABLE watchlist ADD COLUMN take_profit REAL")
    except: pass
    
    # --- Performance Indexes (Step 3 - Phase 6) ---
    for idx_cmd in [
        "CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker)",
        "CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date)",
        "CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON watchlist(ticker)",
        "CREATE INDEX IF NOT EXISTS idx_sentiment_tick ON market_sentiment(ticker)",
        "CREATE INDEX IF NOT EXISTS idx_sentiment_date ON market_sentiment(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_fx_instrument ON forex_trades(instrument)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON price_alerts(ticker)"
    ]:
        try:
            c.execute(idx_cmd)
        except: pass
    try:
        c.execute("ALTER TABLE watchlist ADD COLUMN list_name TEXT DEFAULT 'Principal'")
    except: pass
    try:
        c.execute("ALTER TABLE price_alerts ADD COLUMN session TEXT DEFAULT 'Any'")
    except: pass
    
    # --- Portfolio Migrations (Phase 8) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            type        TEXT DEFAULT 'Standard',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Create default portfolio if empty
    c.execute("SELECT count(*) FROM portfolios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO portfolios (name, description, type) VALUES ('Principal', 'Cartera principal de inversiones', 'Standard')")
        conn.commit()
        
    # Add portfolio_id to all relevant tables
    for table in ["watchlist", "trades", "forex_trades", "price_alerts"]:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN portfolio_id INTEGER DEFAULT 1")
        except: pass
    
    # --- Portfolio Migrations (Phase 8) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            type        TEXT DEFAULT 'Standard',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Create default portfolio if empty
    c.execute("SELECT count(*) FROM portfolios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO portfolios (name, description, type) VALUES ('Principal', 'Cartera principal de inversiones', 'Standard')")
        conn.commit()
        
    # Add portfolio_id to all relevant tables
    for table in ["watchlist", "trades", "forex_trades", "price_alerts"]:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN portfolio_id INTEGER DEFAULT 1")
        except: pass

    # --- Stock Analyses (advanced metrics) ---
    # This table is also in models.py but using raw SQL here to ensure schema matches the raw INSERTs
    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_analyses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT NOT NULL,
            source          TEXT DEFAULT 'generic',
            ticker          TEXT,
            company_name    TEXT,
            price           REAL,
            market_cap      REAL,
            pe_ratio        REAL,
            pe_fwd          REAL,
            eps_actual      REAL,
            eps_estimate    REAL,
            peg_ratio       REAL,
            fcf_yield       REAL,
            ev_ebitda       REAL,
            book_per_share  REAL,
            beta            REAL,
            revenue         REAL,
            revenue_forecast REAL,
            net_income      REAL,
            total_debt      REAL,
            total_equity    REAL,
            profit_margin   REAL,
            revenue_growth  REAL,
            roe             REAL,
            current_ratio   REAL,
            debt_equity     REAL,
            div_yield       REAL,
            one_year_change REAL,
            raw_data        TEXT,
            analyzed_at     TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Investment Notes (qualitative thesis) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS investment_notes (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker              TEXT NOT NULL,
            moat_type           TEXT DEFAULT '',
            moat_rating         INTEGER DEFAULT 0,
            porter_rivalry      TEXT DEFAULT '',
            porter_rivalry_r    INTEGER DEFAULT 0,
            porter_new_entrants TEXT DEFAULT '',
            porter_new_entrants_r INTEGER DEFAULT 0,
            porter_substitutes  TEXT DEFAULT '',
            porter_substitutes_r INTEGER DEFAULT 0,
            porter_buyer_power  TEXT DEFAULT '',
            porter_buyer_power_r INTEGER DEFAULT 0,
            porter_supplier_power TEXT DEFAULT '',
            porter_supplier_power_r INTEGER DEFAULT 0,
            management_notes    TEXT DEFAULT '',
            culture_notes       TEXT DEFAULT '',
            thesis_bull         TEXT DEFAULT '',
            thesis_bear         TEXT DEFAULT '',
            thesis_verdict      TEXT DEFAULT '',
            custom_notes        TEXT DEFAULT '',
            updated_at          TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Workspaces (Layouts - Step 2 - Phase 7) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            config_json TEXT NOT NULL,
            is_active   INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Pre-seed default workspaces if empty
    c.execute("SELECT count(*) FROM workspaces")
    if c.fetchone()[0] == 0:
        import json
        defaults = [
            ("Standard", json.dumps({"performance":True,"risk":True,"precision":True,"psychology":True,"surveillance":True,"scanners":True})),
            ("Risk Focus", json.dumps({"performance":False,"risk":True,"precision":False,"psychology":True,"surveillance":True,"scanners":False})),
            ("Active Trader", json.dumps({"performance":True,"risk":False,"precision":True,"psychology":False,"surveillance":False,"scanners":True}))
        ]
        c.executemany("INSERT INTO workspaces (name, config_json) VALUES (?,?)", defaults)

    # --- Forex / Indices Trades ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS forex_trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date      TEXT NOT NULL,
            instrument      TEXT NOT NULL,
            instrument_type TEXT DEFAULT 'forex',
            direction       TEXT NOT NULL,
            lots            REAL NOT NULL,
            entry_price     REAL NOT NULL,
            exit_price      REAL,
            stop_loss       REAL,
            take_profit     REAL,
            pips            REAL,
            pnl             REAL,
            commission      REAL DEFAULT 0,
            swap            REAL DEFAULT 0,
            strategy        TEXT DEFAULT '',
            timeframe       TEXT DEFAULT '',
            session         TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Price Alerts ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL,
            threshold REAL NOT NULL,
            triggered INTEGER DEFAULT 0,
            triggered_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Migration: add list_name column to watchlist
    try:
        c.execute("ALTER TABLE watchlist ADD COLUMN list_name TEXT DEFAULT 'Principal'")
    except Exception:
        pass  # Column already exists

    # Migration: add post-mortem columns to trades
    for col in ["lecciones", "errores"]:
        try:
            c.execute(f"ALTER TABLE trades ADD COLUMN {col} TEXT DEFAULT ''")
        except Exception:
            pass

    # D1: Add journal upgrade columns to trades table
    for col_def in [
        "ALTER TABLE trades ADD COLUMN hold_time INTEGER DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN risk_pct REAL DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN setup_type TEXT DEFAULT ''",
        "ALTER TABLE trades ADD COLUMN error_type TEXT DEFAULT ''",
        "ALTER TABLE trades ADD COLUMN trade_rating INTEGER DEFAULT 3",
        "ALTER TABLE trades ADD COLUMN stop_loss REAL",
        "ALTER TABLE trades ADD COLUMN take_profit REAL",
        "ALTER TABLE trades ADD COLUMN phase TEXT DEFAULT ''",
        "ALTER TABLE trades ADD COLUMN event TEXT DEFAULT ''",
        "ALTER TABLE trades ADD COLUMN abs_detected INTEGER DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN sot_detected INTEGER DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN dxy_aligned INTEGER DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN vix_context REAL DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN score_fortaleza INTEGER DEFAULT 0",
    ]:
        try:
            c.execute(col_def)
        except Exception:
            pass

    # D1: Add journal upgrade columns to forex_trades table
    for col_def in [
        "ALTER TABLE forex_trades ADD COLUMN hold_time INTEGER DEFAULT 0",
        "ALTER TABLE forex_trades ADD COLUMN setup_type TEXT DEFAULT ''",
        "ALTER TABLE forex_trades ADD COLUMN trade_rating INTEGER DEFAULT 3",
        "ALTER TABLE forex_trades ADD COLUMN phase TEXT DEFAULT ''",
        "ALTER TABLE forex_trades ADD COLUMN event TEXT DEFAULT ''",
        "ALTER TABLE forex_trades ADD COLUMN abs_detected INTEGER DEFAULT 0",
        "ALTER TABLE forex_trades ADD COLUMN sot_detected INTEGER DEFAULT 0",
        "ALTER TABLE forex_trades ADD COLUMN dxy_aligned INTEGER DEFAULT 0",
        "ALTER TABLE forex_trades ADD COLUMN vix_context REAL DEFAULT 0",
        "ALTER TABLE forex_trades ADD COLUMN risk_pct REAL DEFAULT 0",
        "ALTER TABLE forex_trades ADD COLUMN score_fortaleza INTEGER DEFAULT 0",
    ]:
        try:
            c.execute(col_def)
        except Exception:
            pass

    # --- Trading Plan / Journal Entries ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS trading_plan_entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha           TEXT NOT NULL,
            activo          TEXT NOT NULL,
            direccion       TEXT NOT NULL,
            sesgo_1w        TEXT,
            contexto_1d     TEXT,
            gatillo         TEXT,
            confluencias    TEXT,
            entry_price     REAL,
            sl              REAL,
            tp1             REAL,
            tp2             REAL,
            rr_expected     REAL,
            resultado       TEXT,
            r_obtenido       REAL,
            leccion         TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Market Sentiment ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS market_sentiment (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT,
            source      TEXT,
            sentiment   REAL,
            mentions    INTEGER DEFAULT 0,
            headline    TEXT,
            url         TEXT,
            score       REAL,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Macro Metrics (World Bank) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS macro_metrics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator   TEXT,
            country     TEXT,
            value       REAL,
            year        INTEGER,
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Crypto Global Metrics ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS crypto_global (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            market_cap  REAL,
            volume_24h  REAL,
            btc_dominance REAL,
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Analyst Recommendations ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS analyst_recommendations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT UNIQUE,
            strong_buy      INTEGER DEFAULT 0,
            buy             INTEGER DEFAULT 0,
            hold            INTEGER DEFAULT 0,
            sell            INTEGER DEFAULT 0,
            strong_sell      INTEGER DEFAULT 0,
            target_mean     REAL,
            target_median   REAL,
            updated_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- SEC ULTRA FINANCIALS (100+ concepts) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS company_financials_ultra (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT NOT NULL,
            cik             TEXT,
            concept         TEXT NOT NULL,
            period_end      TEXT NOT NULL,
            value           REAL,
            unit            TEXT,
            form            TEXT,
            filed_date      TEXT,
            accn            TEXT,
            fy              INTEGER,
            fp              TEXT,
            recorded_at     TEXT DEFAULT (datetime('now')),
            UNIQUE(ticker, concept, period_end, accn)
        )
    """)

    # --- FRED MACRO HISTORY (80+ series) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS fred_macro_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id       TEXT NOT NULL,
            obs_date        TEXT NOT NULL,
            value           REAL,
            recorded_at     TEXT DEFAULT (datetime('now')),
            UNIQUE(series_id, obs_date)
        )
    """)

    # --- EXTERNAL INTELLIGENCE CACHE (FinViz, etc.) ---
    try:
        c.execute("ALTER TABLE web_scraped_cache RENAME TO external_intel_cache")
    except: pass
    try:
        c.execute("ALTER TABLE external_intel_cache RENAME COLUMN scraped_at TO retrieved_at")
    except: pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS external_intel_cache (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT NOT NULL,
            source          TEXT NOT NULL,
            payload_json    TEXT,
            retrieved_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(ticker, source)
        )
    """)

    # --- INSTITUTIONAL HOLDINGS (Whale Tracker 13F) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS institutional_holdings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT NOT NULL,
            manager_name    TEXT NOT NULL,
            shares          REAL,
            value           REAL,
            report_date     TEXT,
            change_pct      REAL,
            recorded_at     TEXT DEFAULT (datetime('now')),
            UNIQUE(ticker, manager_name, report_date)
        )
    """)

    # --- Performance Indices ---
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_stock_analyzer_ticker ON stock_analyses(ticker)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_stock_analyzer_date ON stock_analyses(analyzed_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_market_sentiment_ticker ON market_sentiment(ticker)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_market_sentiment_date ON market_sentiment(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_inv_notes_ticker ON investment_notes(ticker)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_forex_trades_date ON forex_trades(trade_date)")
    except Exception:
        pass

    conn.commit()
    conn.close()


# ── PORTFOLIO CRUD ──────────────────────────────────────────────────────────
def get_portfolios() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM portfolios ORDER BY id", conn)
    conn.close()
    return df

def add_portfolio(name, desc="", p_type="Standard"):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO portfolios (name, description, type) VALUES (?, ?, ?)", (name, desc, p_type))
    conn.commit()
    conn.close()

def delete_portfolio(p_id):
    if p_id == 1: return # Protected Principal
    conn = get_connection()
    conn.execute("DELETE FROM portfolios WHERE id=?", (p_id,))
    # Manual cascade deletions
    conn.execute("DELETE FROM watchlist WHERE portfolio_id=?", (p_id,))
    conn.execute("DELETE FROM trades WHERE portfolio_id=?", (p_id,))
    conn.execute("DELETE FROM forex_trades WHERE portfolio_id=?", (p_id,))
    conn.execute("DELETE FROM price_alerts WHERE portfolio_id=?", (p_id,))
    conn.commit()
    conn.close()


# ── WATCHLIST ──────────────────────────────────────────────────────────────────
def add_ticker(ticker: str, shares: float = 0, avg_cost: float = 0,
               sector: str = "", notes: str = "", list_name: str = "Principal",
               stop_loss: float = None, take_profit: float = None, industry: str = "",
               target_weight: float = 0.0, portfolio_id: int = 1):
    conn = get_connection()
    try:
        if (not sector or not industry) and yf:
            try:
                info = yf.Ticker(ticker).info
                sector = sector or info.get("sector", "N/A")
                industry = industry or info.get("industry", "N/A")
            except: pass

        # Check if already exists in THIS portfolio
        c = conn.cursor()
        c.execute("SELECT id FROM watchlist WHERE ticker = ? AND portfolio_id = ?", (ticker.upper(), portfolio_id))
        row = c.fetchone()
        if row:
            conn.execute(
                "UPDATE watchlist SET shares=?, avg_cost=?, sector=?, industry=?, notes=?, list_name=?, stop_loss=?, take_profit=?, target_weight=? WHERE id=?",
                (shares, avg_cost, sector, industry, notes, list_name, stop_loss, take_profit, target_weight, row[0])
            )
        else:
            conn.execute(
                "INSERT INTO watchlist (ticker, shares, avg_cost, sector, industry, notes, list_name, stop_loss, take_profit, target_weight, portfolio_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (ticker.upper(), shares, avg_cost, sector, industry, notes, list_name, stop_loss, take_profit, target_weight, portfolio_id)
            )
        conn.commit()
    finally:
        conn.close()


def remove_ticker(ticker: str):
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()


def get_watchlist(portfolio_id: int = 1) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM watchlist WHERE portfolio_id = ? ORDER BY added_at DESC", conn, params=(portfolio_id,))
    conn.close()
    return df


def get_watchlist_lists(portfolio_id: int = 1):
    """Get all distinct list names from watchlist for a specific portfolio"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT list_name FROM watchlist WHERE portfolio_id = ? ORDER BY list_name", (portfolio_id,))
    lists = [row[0] for row in c.fetchall() if row[0]]
    conn.close()
    if not lists:
        lists = ['Principal']
    return lists


def move_ticker_to_list(ticker, list_name):
    """Move a ticker to a different list"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE watchlist SET list_name = ? WHERE ticker = ?", (list_name, ticker))
    conn.commit()
    conn.close()


def get_watchlist_by_list(list_name=None, portfolio_id=1):
    """Get watchlist filtered by list name and portfolio_id"""
    conn = get_connection()
    if list_name and list_name != 'Todas':
        df = pd.read_sql("SELECT * FROM watchlist WHERE list_name = ? AND portfolio_id = ? ORDER BY added_at DESC", 
                         conn, params=(list_name, portfolio_id))
    else:
        df = pd.read_sql("SELECT * FROM watchlist WHERE portfolio_id = ? ORDER BY added_at DESC", 
                         conn, params=(portfolio_id,))
    conn.close()
    return df


def update_ticker(ticker: str, shares: float, avg_cost: float,
                  sector: str, notes: str, industry: str = "", portfolio_id: int = 1):
    conn = get_connection()
    conn.execute(
        "UPDATE watchlist SET shares=?, avg_cost=?, sector=?, industry=?, notes=? WHERE ticker=? AND portfolio_id=?",
        (shares, avg_cost, sector, industry, notes, ticker.upper(), portfolio_id)
    )
    conn.commit()
    conn.close()


# ── TRADES ─────────────────────────────────────────────────────────────────────
def add_trade(trade_date, ticker, trade_type, entry_price,
              exit_price, shares, strategy, psych_notes,
              lecciones="", errores="",
              setup_type="", error_type="", trade_rating=3,
              stop_loss=None, take_profit=None,
              risk_pct=0.0, phase="", event="",
              abs_detected=0, sot_detected=0, dxy_aligned=0,
              vix_context=0.0, score_fortaleza=0,
              portfolio_id: int = 1):
    pnl, pnl_pct = None, None
    if exit_price and exit_price > 0:
        if trade_type == "Compra":
            pnl = (exit_price - entry_price) * shares
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            pnl = (entry_price - exit_price) * shares
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100

    conn = get_connection()
    conn.execute(
        """INSERT INTO trades
           (trade_date, ticker, trade_type, entry_price, exit_price,
            shares, pnl, pnl_pct, strategy, psych_notes, lecciones, errores,
            setup_type, error_type, trade_rating, stop_loss, take_profit,
            risk_pct, phase, event, abs_detected, sot_detected, dxy_aligned, vix_context, score_fortaleza, portfolio_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(trade_date), ticker.upper(), trade_type, entry_price,
         exit_price, shares, pnl, pnl_pct, strategy, psych_notes,
         lecciones, errores, setup_type, error_type, trade_rating,
         stop_loss, take_profit, risk_pct, phase, event, abs_detected,
         sot_detected, dxy_aligned, vix_context, score_fortaleza, portfolio_id)
    )
    conn.commit()
    conn.close()


def get_trades(portfolio_id: int = 1) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM trades WHERE portfolio_id = ? ORDER BY trade_date DESC", conn, params=(portfolio_id,))
    conn.close()
    return df


def delete_trade(trade_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM trades WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()


# ── PDF ANALYSES ───────────────────────────────────────────────────────────────
def save_analysis(filename, ticker, revenue, net_income, total_debt,
                  total_equity, profit_margin, revenue_growth,
                  pe_ratio, roe, current_ratio, raw_text):
    conn = get_connection()
    conn.execute(
        """INSERT INTO pdf_analyses
           (filename, ticker, revenue, net_income, total_debt, total_equity,
            profit_margin, revenue_growth, pe_ratio, roe, current_ratio, raw_text)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (filename, ticker.upper(), revenue, net_income, total_debt,
         total_equity, profit_margin, revenue_growth, pe_ratio,
         roe, current_ratio, raw_text)
    )
    conn.commit()
    conn.close()


def get_analyses() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql(
        "SELECT * FROM pdf_analyses ORDER BY analyzed_at DESC", conn)
    conn.close()
    return df


# ── STOCK ANALYSES (expanded) ────────────────────────────────────────────────
def save_stock_analysis(flat: dict, filename: str):
    """Save a flattened parsed analysis to the stock_analyses table."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO stock_analyses
           (filename, source, ticker, company_name, price, market_cap,
            pe_ratio, pe_fwd, eps_actual, eps_estimate, peg_ratio, fcf_yield,
            ev_ebitda, book_per_share, beta, revenue, revenue_forecast,
            net_income, total_debt, total_equity, profit_margin,
            revenue_growth, roe, current_ratio, debt_equity,
            div_yield, one_year_change, raw_data)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (filename, flat.get("source", "generic"),
         flat.get("ticker", ""), flat.get("company_name", ""),
         flat.get("price"), flat.get("market_cap"),
         flat.get("pe_ratio"), flat.get("pe_fwd"),
         flat.get("eps_actual"), flat.get("eps_estimate"),
         flat.get("peg_ratio"), flat.get("fcf_yield"),
         flat.get("ev_ebitda"), flat.get("book_per_share"),
         flat.get("beta"), flat.get("revenue"),
         flat.get("revenue_forecast"), flat.get("net_income"),
         flat.get("total_debt"), flat.get("total_equity"),
         flat.get("profit_margin"), flat.get("revenue_growth"),
         flat.get("roe"), flat.get("current_ratio"),
         flat.get("debt_equity"), flat.get("div_yield"),
         flat.get("one_year_change"),
         flat.get("raw_data", ""))
    )
    conn.commit()
    conn.close()


def get_stock_analyses() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM stock_analyses ORDER BY analyzed_at DESC", conn)
    conn.close()
    return df


def get_stock_analysis(analysis_id: int) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM stock_analyses WHERE id=?", (analysis_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}


def delete_stock_analysis(analysis_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM stock_analyses WHERE id=?", (analysis_id,))
    conn.commit()
    conn.close()


# ── INVESTMENT NOTES ─────────────────────────────────────────────────────────
def save_investment_notes(ticker: str, notes: dict):
    """Save or update investment notes for a ticker."""
    conn = get_connection()
    # Upsert: delete old, insert new
    conn.execute("DELETE FROM investment_notes WHERE ticker=?", (ticker.upper(),))
    conn.execute(
        """INSERT INTO investment_notes
           (ticker, moat_type, moat_rating,
            porter_rivalry, porter_rivalry_r,
            porter_new_entrants, porter_new_entrants_r,
            porter_substitutes, porter_substitutes_r,
            porter_buyer_power, porter_buyer_power_r,
            porter_supplier_power, porter_supplier_power_r,
            management_notes, culture_notes,
            thesis_bull, thesis_bear, thesis_verdict, custom_notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ticker.upper(),
         notes.get("moat_type", ""), notes.get("moat_rating", 0),
         notes.get("porter_rivalry", ""), notes.get("porter_rivalry_r", 0),
         notes.get("porter_new_entrants", ""), notes.get("porter_new_entrants_r", 0),
         notes.get("porter_substitutes", ""), notes.get("porter_substitutes_r", 0),
         notes.get("porter_buyer_power", ""), notes.get("porter_buyer_power_r", 0),
         notes.get("porter_supplier_power", ""), notes.get("porter_supplier_power_r", 0),
         notes.get("management_notes", ""), notes.get("culture_notes", ""),
         notes.get("thesis_bull", ""), notes.get("thesis_bear", ""),
         notes.get("thesis_verdict", ""), notes.get("custom_notes", ""))
    )
    conn.commit()
    conn.close()


def get_investment_notes(ticker: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM investment_notes WHERE ticker=? ORDER BY updated_at DESC LIMIT 1",
        (ticker.upper(),)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}


def get_all_investment_notes() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM investment_notes ORDER BY updated_at DESC", conn)
    conn.close()
    return df


# ── TICKER HISTORY (evolution comparison) ──────────────────────────────────────
def get_ticker_history(ticker: str) -> pd.DataFrame:
    """Get all analyses for a specific ticker, ordered by date."""
    conn = get_connection()
    df = pd.read_sql(
        "SELECT * FROM stock_analyses WHERE ticker=? ORDER BY analyzed_at ASC",
        conn, params=(ticker.upper(),)
    )
    conn.close()
    return df


def get_analyzed_tickers() -> list:
    """Get list of unique tickers that have been analyzed."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM stock_analyses WHERE ticker != '' ORDER BY ticker"
    ).fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


# ── FOREX / INDICES TRADES ────────────────────────────────────────────────────
def add_forex_trade(trade_date, instrument, instrument_type, direction,
                    lots, entry_price, exit_price, stop_loss, take_profit,
                    pips, pnl, commission, swap, strategy, timeframe, session, notes,
                    setup_type="", trade_rating=3,
                    phase="", event="", abs_detected=0, sot_detected=0,
                    dxy_aligned=0, vix_context=0.0, risk_pct=0.0, score_fortaleza=0,
                    portfolio_id: int = 1):
    conn = get_connection()
    conn.execute(
        """INSERT INTO forex_trades
           (trade_date, instrument, instrument_type, direction, lots,
            entry_price, exit_price, stop_loss, take_profit, pips, pnl,
            commission, swap, strategy, timeframe, session, notes,
            setup_type, trade_rating, phase, event, abs_detected,
            sot_detected, dxy_aligned, vix_context, risk_pct, score_fortaleza, portfolio_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(trade_date), instrument.upper(), instrument_type, direction,
         lots, entry_price, exit_price, stop_loss, take_profit,
         pips, pnl, commission, swap, strategy, timeframe, session, notes,
         setup_type, trade_rating, phase, event, abs_detected,
         sot_detected, dxy_aligned, vix_context, risk_pct, score_fortaleza, portfolio_id)
    )
    conn.commit()
    conn.close()


def get_forex_trades(portfolio_id: int = 1) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM forex_trades WHERE portfolio_id = ? ORDER BY trade_date DESC", conn, params=(portfolio_id,))
    conn.close()
    return df


def save_workspace(name: str, config_dict: dict):
    import json
    conn = get_connection()
    config_json = json.dumps(config_dict)
    conn.execute("INSERT OR REPLACE INTO workspaces (name, config_json) VALUES (?, ?)", (name, config_json))
    conn.commit()
    conn.close()

def get_workspaces() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM workspaces", conn)
    conn.close()
    return df

def delete_workspace(name: str):
    conn = get_connection()
    conn.execute("DELETE FROM workspaces WHERE name=?", (name,))
    conn.commit()
    conn.close()


# ── PRICE ALERTS ──────────────────────────────────────────────────────────────
def add_alert(ticker: str, direction: str, threshold: float, session: str = "Any", alert_type: str = "fixed", multiplier: float = 0.0, portfolio_id: int = 1):
    conn = get_connection()
    conn.execute(
        "INSERT INTO price_alerts (ticker, direction, threshold, session, alert_type, multiplier, portfolio_id) VALUES (?,?,?,?,?,?,?)",
        (ticker.upper(), direction, threshold, session, alert_type, multiplier, portfolio_id)
    )
    conn.commit()
    conn.close()


def get_alerts(portfolio_id: int = 1) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM price_alerts WHERE portfolio_id = ? ORDER BY created_at DESC", conn, params=(portfolio_id,))
    conn.close()
    return df


def delete_alert(alert_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM price_alerts WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


def mark_triggered(alert_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE price_alerts SET triggered=1, triggered_at=datetime('now') WHERE id=?",
        (alert_id,)
    )
    conn.close()

# ── MARKET SENTIMENT ──────────────────────────────────────────────────────────
def save_sentiment(ticker: str, source: str, sentiment: float, mentions: int = 0,
                   headline: str = "", url: str = "", score: float = 0):
    conn = get_connection()
    conn.execute(
        "INSERT INTO market_sentiment (ticker, source, sentiment, mentions, headline, url, score) VALUES (?,?,?,?,?,?,?)",
        (ticker.upper() if ticker else None, source, sentiment, mentions, headline, url, score)
    )
    conn.commit()
    conn.close()

def get_latest_sentiment(ticker: str = None, limit: int = 20) -> pd.DataFrame:
    conn = get_connection()
    if ticker:
        query = "SELECT * FROM market_sentiment WHERE ticker = ? ORDER BY created_at DESC LIMIT ?"
        df = pd.read_sql(query, conn, params=(ticker.upper(), limit))
    else:
        query = "SELECT * FROM market_sentiment ORDER BY created_at DESC LIMIT ?"
        df = pd.read_sql(query, conn, params=(limit,))
    conn.close()
    return df

def get_sentiment_trend(days: int = 7) -> pd.DataFrame:
    """Returns daily average sentiment score for horizontal trend analysis."""
    conn = get_connection()
    query = """
        SELECT date(created_at) as date, AVG(score) as avg_score, COUNT(*) as count
        FROM market_sentiment
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at)
        ORDER BY date ASC
    """
    df = pd.read_sql(query, conn, params=(f'-{days} days',))
    conn.close()
    return df

# ── MACRO METRICS ─────────────────────────────────────────────────────────────
def save_macro_metric(indicator: str, country: str, value: float, year: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO macro_metrics (indicator, country, value, year) VALUES (?,?,?,?)",
        (indicator, country, value, year)
    )
    conn.commit()
    conn.close()

def get_macro_metrics(indicator: str = None) -> pd.DataFrame:
    conn = get_connection()
    if indicator:
        df = pd.read_sql("SELECT * FROM macro_metrics WHERE indicator = ? ORDER BY year DESC", conn, params=(indicator,))
    else:
        df = pd.read_sql("SELECT * FROM macro_metrics ORDER BY updated_at DESC", conn)
    conn.close()
    return df

# ── CRYPTO GLOBAL ─────────────────────────────────────────────────────────────
def save_crypto_global(market_cap: float, volume_24h: float, btc_dominance: float):
    conn = get_connection()
    conn.execute(
        "INSERT INTO crypto_global (market_cap, volume_24h, btc_dominance) VALUES (?,?,?)",
        (market_cap, volume_24h, btc_dominance)
    )
    conn.commit()
    conn.close()

def get_latest_crypto_global():
    conn = get_connection()
    row = conn.execute("SELECT * FROM crypto_global ORDER BY updated_at DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

# ── ANALYST RECOMMENDATIONS ───────────────────────────────────────────────────
def save_analyst_recommendation(ticker: str, data: dict):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO analyst_recommendations
           (ticker, strong_buy, buy, hold, sell, strong_sell, target_mean, target_median, updated_at)
           VALUES (?,?,?,?,?,?,?,?,datetime('now'))""",
        (ticker.upper(), data.get('strong_buy', 0), data.get('buy', 0),
         data.get('hold', 0), data.get('sell', 0), data.get('strong_sell', 0),
         data.get('target_mean'), data.get('target_median'))
    )
    conn.commit()
    conn.close()

def get_analyst_recommendation(ticker: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM analyst_recommendations WHERE ticker = ?", (ticker.upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None

# ── SEC ULTRA FINANCIALS ──────────────────────────────────────────────────────
def save_ultra_financials(ticker: str, cik: str, data_list: list):
    conn = get_connection()
    try:
        conn.executemany("""
            INSERT OR REPLACE INTO company_financials_ultra 
            (ticker, cik, concept, period_end, value, unit, form, filed_date, accn, fy, fp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(ticker.upper(), cik, d["concept"], d["end"], d["val"], d["unit"], 
               d.get("form"), d.get("filed"), d.get("accn"), d.get("fy"), d.get("fp")) 
              for d in data_list])
        conn.commit()
    finally:
        conn.close()

def get_ultra_financials(ticker: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM company_financials_ultra WHERE ticker = ? ORDER BY period_end DESC", 
                     conn, params=(ticker.upper(),))
    conn.close()
    return df

# ── FRED MACRO HISTORY ────────────────────────────────────────────────────────
def save_macro_history(series_id: str, observations: list):
    conn = get_connection()
    try:
        conn.executemany("""
            INSERT OR REPLACE INTO fred_macro_history (series_id, obs_date, value)
            VALUES (?, ?, ?)
        """, [(series_id, obs["date"], obs["value"]) for obs in observations])
        conn.commit()
    finally:
        conn.close()

def get_macro_history(series_id: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM fred_macro_history WHERE series_id = ? ORDER BY obs_date DESC", 
                     conn, params=(series_id,))
    conn.close()
    return df

# ── EXTERNAL INTELLIGENCE CACHE ───────────────────────────────────────────────────
def save_external_intelligence(ticker: str, source: str, payload: dict):
    from json import dumps
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO external_intel_cache (ticker, source, payload_json)
        VALUES (?, ?, ?)
    """, (ticker.upper(), source, dumps(payload)))
    conn.commit()
    conn.close()

def get_external_intelligence(ticker: str, source: str) -> dict:
    from json import loads
    conn = get_connection()
    row = conn.execute("SELECT payload_json FROM external_intel_cache WHERE ticker = ? AND source = ?", 
                       (ticker.upper(), source)).fetchone()
    conn.close()
    return loads(row[0]) if row else None

# ── INSTITUTIONAL HOLDINGS ────────────────────────────────────────────────────
def save_institutional_holdings(ticker: str, holdings: list):
    conn = get_connection()
    try:
        conn.executemany("""
            INSERT OR REPLACE INTO institutional_holdings 
            (ticker, manager_name, shares, value, report_date, change_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(ticker.upper(), h["manager"], h["shares"], h.get("value"), 
               h.get("date"), h.get("change")) for h in holdings])
        conn.commit()
    finally:
        conn.close()

def get_institutional_holdings(ticker: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM institutional_holdings WHERE ticker = ? ORDER BY value DESC", 
                     conn, params=(ticker.upper(),))
    conn.close()
    return df
