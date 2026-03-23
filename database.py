"""
database.py - SQLite setup and all CRUD operations
Investment Command Center — Quantum Retail Terminal
"""
import sqlite3
import json
import pandas as pd
import os

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    # --- Watchlist / Portfolio ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL UNIQUE,
            shares      REAL DEFAULT 0,
            avg_cost    REAL DEFAULT 0,
            sector      TEXT DEFAULT '',
            notes       TEXT DEFAULT '',
            added_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Trading Journal ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date      TEXT NOT NULL,
            ticker          TEXT NOT NULL,
            trade_type      TEXT NOT NULL,
            entry_price     REAL NOT NULL,
            exit_price      REAL,
            shares          REAL NOT NULL,
            pnl             REAL,
            pnl_pct         REAL,
            strategy        TEXT DEFAULT '',
            psych_notes     TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- PDF Analysis Results ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS pdf_analyses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT NOT NULL,
            ticker          TEXT DEFAULT '',
            revenue         REAL,
            net_income      REAL,
            total_debt      REAL,
            total_equity    REAL,
            profit_margin   REAL,
            revenue_growth  REAL,
            pe_ratio        REAL,
            roe             REAL,
            current_ratio   REAL,
            raw_text        TEXT,
            analyzed_at     TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Stock Analyses (expanded, replaces pdf_analyses for new reports) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_analyses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT NOT NULL,
            source          TEXT DEFAULT 'generic',
            ticker          TEXT DEFAULT '',
            company_name    TEXT DEFAULT '',
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
        conn.commit()
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
    ]:
        try:
            c.execute(col_def)
        except Exception:
            pass

    conn.commit()
    conn.close()


# ── WATCHLIST ──────────────────────────────────────────────────────────────────
def add_ticker(ticker: str, shares: float = 0, avg_cost: float = 0,
               sector: str = "", notes: str = "", list_name: str = "Principal"):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, shares, avg_cost, sector, notes, list_name) VALUES (?,?,?,?,?,?)",
            (ticker.upper(), shares, avg_cost, sector, notes, list_name)
        )
        conn.commit()
    finally:
        conn.close()


def remove_ticker(ticker: str):
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()


def get_watchlist() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM watchlist ORDER BY added_at DESC", conn)
    conn.close()
    return df


def get_watchlist_lists():
    """Get all distinct list names from watchlist"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT list_name FROM watchlist ORDER BY list_name")
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


def get_watchlist_by_list(list_name=None):
    """Get watchlist filtered by list name"""
    conn = get_connection()
    if list_name and list_name != 'Todas':
        df = pd.read_sql("SELECT * FROM watchlist WHERE list_name = ? ORDER BY added_at DESC", conn, params=(list_name,))
    else:
        df = pd.read_sql("SELECT * FROM watchlist ORDER BY added_at DESC", conn)
    conn.close()
    return df


def update_ticker(ticker: str, shares: float, avg_cost: float,
                  sector: str, notes: str):
    conn = get_connection()
    conn.execute(
        "UPDATE watchlist SET shares=?, avg_cost=?, sector=?, notes=? WHERE ticker=?",
        (shares, avg_cost, sector, notes, ticker.upper())
    )
    conn.commit()
    conn.close()


# ── TRADES ─────────────────────────────────────────────────────────────────────
def add_trade(trade_date, ticker, trade_type, entry_price,
              exit_price, shares, strategy, psych_notes,
              lecciones="", errores="",
              setup_type="", error_type="", trade_rating=3,
              stop_loss=None, take_profit=None):
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
            setup_type, error_type, trade_rating, stop_loss, take_profit)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(trade_date), ticker.upper(), trade_type, entry_price,
         exit_price, shares, pnl, pnl_pct, strategy, psych_notes,
         lecciones, errores, setup_type, error_type, trade_rating,
         stop_loss, take_profit)
    )
    conn.commit()
    conn.close()


def get_trades() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM trades ORDER BY trade_date DESC", conn)
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
                    setup_type="", trade_rating=3):
    conn = get_connection()
    conn.execute(
        """INSERT INTO forex_trades
           (trade_date, instrument, instrument_type, direction, lots,
            entry_price, exit_price, stop_loss, take_profit, pips, pnl,
            commission, swap, strategy, timeframe, session, notes,
            setup_type, trade_rating)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(trade_date), instrument.upper(), instrument_type, direction,
         lots, entry_price, exit_price, stop_loss, take_profit,
         pips, pnl, commission, swap, strategy, timeframe, session, notes,
         setup_type, trade_rating)
    )
    conn.commit()
    conn.close()


def get_forex_trades() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM forex_trades ORDER BY trade_date DESC", conn)
    conn.close()
    return df


def delete_forex_trade(trade_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM forex_trades WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()


# ── PRICE ALERTS ──────────────────────────────────────────────────────────────
def add_alert(ticker: str, direction: str, threshold: float):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO price_alerts (ticker, direction, threshold) VALUES (?,?,?)",
            (ticker.upper(), direction, threshold)
        )
        conn.commit()
    finally:
        conn.close()


def get_alerts() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM price_alerts ORDER BY created_at DESC", conn)
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
    conn.commit()
    conn.close()
