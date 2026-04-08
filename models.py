from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy import create_engine
import datetime
import os

Base = declarative_base()

# Database Path Configuration (matching existing logic)
_app_dir = os.path.dirname(__file__)
_db_in_app = os.path.join(_app_dir, "investment_data.db")
if os.path.isfile(_db_in_app) and os.access(_app_dir, os.W_OK):
    DB_PATH = _db_in_app
elif os.access(_app_dir, os.W_OK):
    DB_PATH = _db_in_app
else:
    DB_PATH = os.path.join("/tmp", "investment_data.db")

ENGINE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(ENGINE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Watchlist(Base):
    __tablename__ = "watchlist"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, nullable=False, index=True)
    shares = Column(Float, default=0.0)
    avg_cost = Column(Float, default=0.0)
    sector = Column(String, default="")
    notes = Column(Text, default="")
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    trade_date = Column(String, nullable=False)
    ticker = Column(String, nullable=False, index=True)
    trade_type = Column(String, nullable=False) # BUY/SELL
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    shares = Column(Float, nullable=False)
    pnl = Column(Float)
    pnl_pct = Column(Float)
    strategy = Column(String, default="")
    psych_notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class StockAnalysis(Base):
    __tablename__ = "stock_analyses"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    source = Column(String, default="generic")
    ticker = Column(String, index=True)
    company_name = Column(String)
    price = Column(Float)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    pe_fwd = Column(Float)
    eps_actual = Column(Float)
    eps_estimate = Column(Float)
    peg_ratio = Column(Float)
    fcf_yield = Column(Float)
    ev_ebitda = Column(Float)
    book_per_share = Column(Float)
    revenue_growth = Column(Float)
    net_income_growth = Column(Float)
    roe = Column(Float)
    roic = Column(Float)
    debt_equity = Column(Float)
    current_ratio = Column(Float)
    payout_ratio = Column(Float)
    dividend_yield = Column(Float)
    summary = Column(Text)
    moat_rating = Column(String)
    risk_level = Column(String)
    raw_response = Column(Text)
    analyzed_at = Column(DateTime, default=datetime.datetime.utcnow)

class InvestmentNote(Base):
    __tablename__ = "investment_notes"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    title = Column(String)
    content = Column(Text)
    category = Column(String, default="General") # Fundamental, Macro, Technical
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ForexTrade(Base):
    __tablename__ = "forex_trades"
    id = Column(Integer, primary_key=True, index=True)
    pair = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    units = Column(Float, nullable=False)
    pnl = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PriceAlert(Base):
    __tablename__ = "price_alerts"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    target_price = Column(Float, nullable=False)
    condition = Column(String, default="above") # above/below
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

def init_models():
    Base.metadata.create_all(bind=engine)
