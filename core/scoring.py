"""core/scoring.py - Unified Quant Scoring System (Finterm Light)."""
import os
import sys
from dataclasses import dataclass, field

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

@dataclass
class ScoreComponents:
    fundamental: float = 50.0   # 0-100
    technical:   float = 50.0   # 0-100
    sentiment:   float = 50.0   # 0-100
    risk:        float = 50.0   # 0-100
    smart_money: float = 50.0   # 0-100

    _weights: dict = field(default_factory=lambda: {
        "fundamental": 0.30,
        "technical":   0.25,
        "sentiment":   0.20,
        "risk":        0.15,
        "smart_money": 0.10,
    })

    @property
    def total(self) -> float:
        w = self._weights
        return round(
            self.fundamental * w["fundamental"] +
            self.technical   * w["technical"]   +
            self.sentiment   * w["sentiment"]   +
            self.risk        * w["risk"]        +
            self.smart_money * w["smart_money"],
            2,
        )

    @property
    def label(self) -> str:
        t = self.total
        if t >= 75: return "STRONG BUY"
        if t >= 60: return "BUY"
        if t >= 45: return "NEUTRAL"
        if t >= 30: return "SELL"
        return "STRONG SELL"

    def to_dict(self) -> dict:
        return {
            "Total":       self.total,
            "Recomendación": self.label,
            "Fundamental": self.fundamental,
            "Técnico":   self.technical,
            "Sentimiento":   self.sentiment,
            "Riesgo":        self.risk,
            "Smart Money": self.smart_money,
            "Breakdown": {
                "Fundamental": self.fundamental,
                "Technical": self.technical,
                "Sentiment": self.sentiment,
                "Risk": self.risk,
                "SmartMoney": self.smart_money
            }
        }

def calculate_fundamental_score(info: dict) -> float:
    score = 50.0
    try:
        pe = info.get("trailingPE")
        if pe and 0 < pe < 15: score += 15
        elif pe and pe > 30: score -= 15
        
        roe = info.get("returnOnEquity")
        if roe and roe > 0.15: score += 10
        elif roe and roe < 0: score -= 10
        
        margin = info.get("profitMargins")
        if margin and margin > 0.15: score += 15
        elif margin and margin < 0: score -= 10
        
        de = info.get("debtToEquity")
        if de and de < 50: score += 10
        elif de and de > 150: score -= 10
    except Exception: pass
    return max(0.0, min(100.0, score))

def calculate_technical_score(info: dict) -> float:
    score = 50.0
    try:
        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        ma50 = info.get("fiftyDayAverage")
        ma200 = info.get("twoHundredDayAverage")
        
        if price and ma50 and price > ma50: score += 20
        elif price and ma50 and price < ma50: score -= 10
        
        if ma50 and ma200 and ma50 > ma200: score += 15
        elif ma50 and ma200 and ma50 < ma200: score -= 15
        
        high52 = info.get("fiftyTwoWeekHigh")
        if price and high52 and price > high52 * 0.9: score += 15
        elif price and high52 and price < high52 * 0.7: score -= 15
    except Exception: pass
    return max(0.0, min(100.0, score))

def calculate_risk_score(info: dict) -> float:
    score = 50.0
    try:
        beta = info.get("beta")
        if beta and beta < 0.8: score += 20
        elif beta and beta > 1.5: score -= 20
        
        cr = info.get("currentRatio")
        if cr and cr > 1.5: score += 15
        elif cr and cr < 1: score -= 15
    except Exception: pass
    return max(0.0, min(100.0, score))

def calculate_smart_money_score(info: dict) -> float:
    score = 50.0
    try:
        inst = info.get("heldPercentInstitutions")
        if inst and inst > 0.6: score += 20
        elif inst and inst < 0.2: score -= 15
        
        insider = info.get("heldPercentInsiders")
        if insider and insider > 0.05: score += 20
        
        short = info.get("shortRatio")
        if short and short < 3: score += 10
        elif short and short > 8: score -= 20
    except Exception: pass
    return max(0.0, min(100.0, score))

def get_full_analysis(ticker: str, info: dict, skip_sentiment: bool = False) -> dict:
    sentiment_score = 50.0
    if not skip_sentiment:
        try:
            from services.local_sentiment import analyze_ticker_sentiment, normalize_sentiment
            raw_sentiment = analyze_ticker_sentiment(ticker, hours_back=48)
            sentiment_score = normalize_sentiment(raw_sentiment["score"]) if raw_sentiment else 50.0
        except Exception:
            pass
        
    sc = ScoreComponents(
        fundamental=calculate_fundamental_score(info),
        technical=calculate_technical_score(info),
        sentiment=sentiment_score,
        risk=calculate_risk_score(info),
        smart_money=calculate_smart_money_score(info),
    )
    return sc.to_dict()
