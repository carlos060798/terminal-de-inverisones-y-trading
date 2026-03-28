"""ML Engine — Lightweight neural models for Quantum Retail Terminal.
Uses scikit-learn only. No GPU required. Trains in <2 seconds."""

import numpy as np
import pandas as pd
from pathlib import Path
import os

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor, IsolationForest
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

MODEL_DIR = Path(__file__).parent / "ml_models"

# S&P 100 tickers for training
SP100 = ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","BRK-B","JPM","V","MA",
         "UNH","JNJ","PG","HD","COST","XOM","ABBV","MRK","PFE","KO",
         "PEP","WMT","CSCO","CRM","ADBE","AMD","INTC","NFLX","DIS","NKE",
         "BA","CAT","GE","HON","GS","MS","BAC","WFC","BLK","SCHW",
         "LLY","TMO","ABT","BMY","AMGN","GILD","CVX","COP","SLB","NEE"]

FEATURE_COLS = ['pe','fwd_pe','pb','ps','roe','roa','margin','debt_equity',
                'rev_growth','earn_growth','div_yield','beta','current_ratio','quick_ratio']


def _get_features(ticker):
    """Extract features from a single ticker. Returns dict or None."""
    try:
        info = yf.Ticker(ticker).info
        return {
            'pe': info.get('trailingPE', 0) or 0,
            'fwd_pe': info.get('forwardPE', 0) or 0,
            'pb': info.get('priceToBook', 0) or 0,
            'ps': info.get('priceToSalesTrailing12Months', 0) or 0,
            'roe': info.get('returnOnEquity', 0) or 0,
            'roa': info.get('returnOnAssets', 0) or 0,
            'margin': info.get('profitMargins', 0) or 0,
            'debt_equity': info.get('debtToEquity', 0) or 0,
            'rev_growth': info.get('revenueGrowth', 0) or 0,
            'earn_growth': info.get('earningsGrowth', 0) or 0,
            'div_yield': info.get('dividendYield', 0) or 0,
            'beta': info.get('beta', 1) or 1,
            'current_ratio': info.get('currentRatio', 0) or 0,
            'quick_ratio': info.get('quickRatio', 0) or 0,
        }
    except Exception:
        return None


class QualityClassifier:
    """Random Forest that classifies stocks as Excellent/Good/Regular/Poor."""
    def __init__(self):
        try:
            self.model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
            self.scaler = StandardScaler()
            self.trained = False
        except Exception:
            self.model = None
            self.scaler = None
            self.trained = False

    def train(self, features_df, labels):
        try:
            X = self.scaler.fit_transform(features_df)
            self.model.fit(X, labels)
            self.trained = True
        except Exception:
            self.trained = False

    def predict(self, features_dict):
        try:
            if not self.trained:
                return None, 0
            df = pd.DataFrame([features_dict])
            X = self.scaler.transform(df)
            pred = self.model.predict(X)[0]
            proba = max(self.model.predict_proba(X)[0])
            return pred, round(proba * 100, 1)
        except Exception:
            return None, 0


class AnomalyDetector:
    """Isolation Forest to detect fundamental anomalies vs sector."""
    def __init__(self):
        try:
            self.model = IsolationForest(n_estimators=50, contamination=0.1, random_state=42)
            self.scaler = StandardScaler()
            self.trained = False
        except Exception:
            self.model = None
            self.scaler = None
            self.trained = False

    def train(self, features_df):
        try:
            X = self.scaler.fit_transform(features_df)
            self.model.fit(X)
            self.trained = True
        except Exception:
            self.trained = False

    def detect(self, features_dict):
        try:
            if not self.trained:
                return []
            df = pd.DataFrame([features_dict])
            X = self.scaler.transform(df)
            score = self.model.score_samples(X)[0]
            # Find which features are most anomalous
            anomalies = []
            means = self.scaler.mean_
            stds = self.scaler.scale_
            for i, (col, val) in enumerate(features_dict.items()):
                z = abs((val - means[i]) / max(stds[i], 0.001))
                if z > 1.5:
                    direction = "por encima" if val > means[i] else "por debajo"
                    anomalies.append({"metric": col, "z_score": round(z, 1), "direction": direction, "value": val})
            return sorted(anomalies, key=lambda x: x['z_score'], reverse=True)[:5]
        except Exception:
            return []


class SmartScorer:
    """Gradient Boosting that learns optimal factor weights for stock scoring."""
    def __init__(self):
        try:
            self.model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
            self.scaler = StandardScaler()
            self.trained = False
        except Exception:
            self.model = None
            self.scaler = None
            self.trained = False

    def train(self, features_df, returns_1y):
        try:
            X = self.scaler.fit_transform(features_df)
            self.model.fit(X, returns_1y)
            self.trained = True
        except Exception:
            self.trained = False

    def score(self, features_dict):
        try:
            if not self.trained:
                return 50
            df = pd.DataFrame([features_dict])
            X = self.scaler.transform(df)
            raw = self.model.predict(X)[0]
            # Normalize to 0-100
            return max(0, min(100, int(50 + raw * 200)))
        except Exception:
            return 50

    def feature_importance(self):
        try:
            if not self.trained:
                return {}
            return dict(zip(FEATURE_COLS, self.model.feature_importances_))
        except Exception:
            return {}



class PeterLynchClassifier:
    """Random Forest to classify stocks into Peter Lynch profiles (Stalwart, Fast Grower, etc)."""
    def __init__(self):
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler
            self.model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
            self.scaler = StandardScaler()
            self.trained = False
        except Exception:
            self.model = None
            self.scaler = None
            self.trained = False

    def train(self, features_df):
        """Heuristically label the SP100 data to train the RF model."""
        try:
            labels = []
            for _, row in features_df.iterrows():
                growth = row.get("rev_growth", 0)
                div = row.get("div_yield", 0)
                # Lynch logic rough heuristic for training
                if growth > 0.15:
                    labels.append("Fast Grower")
                elif growth > 0.05:
                    if div > 0.02:
                        labels.append("Stalwart")
                    else:
                        labels.append("Cyclical")
                else:
                    labels.append("Slow Grower")

            X = self.scaler.fit_transform(features_df)
            self.model.fit(X, labels)
            self.trained = True
        except Exception:
            self.trained = False

    def predict(self, features_dict):
        try:
            if not self.trained:
                return "Unknown", 0
            df = import_pandas()(features_dict)
            X = self.scaler.transform(df)
            pred = self.model.predict(X)[0]
            proba = max(self.model.predict_proba(X)[0])
            return pred, round(proba * 100, 1)
        except Exception:
            return "Unknown", 0

def import_pandas():
    import pandas as pd
    return lambda d: pd.DataFrame([d])


    # Singleton instances with Streamlit cache
    try:
        import streamlit as _st

        @_st.cache_resource
        def get_models():
            if not HAS_SKLEARN:
                return None, None, None, None
            return QualityClassifier(), AnomalyDetector(), SmartScorer(), PeterLynchClassifier()
    except ImportError:
        # Fallback without Streamlit
        _quality = None
        _anomaly = None
        _scorer = None
        _lynch = None

        def get_models():
            global _quality, _anomaly, _scorer, _lynch
            if not HAS_SKLEARN:
                return None, None, None, None
            if _quality is None:
                _quality = QualityClassifier()
                _anomaly = AnomalyDetector()
                _scorer = SmartScorer()
                _lynch = PeterLynchClassifier()
            return _quality, _anomaly, _scorer, _lynch


def train_models(progress_callback=None):
    """Train all models using S&P 100 data. Call once per session."""
    try:
        quality, anomaly, scorer, lynch = get_models()
        if quality is None:
            return False

        # Check cache
        MODEL_DIR.mkdir(exist_ok=True)
        cache_file = MODEL_DIR / "training_data.pkl"

        if HAS_JOBLIB and cache_file.exists():
            data = joblib.load(cache_file)
            features_df = data['features']
            labels = data['labels']
            returns = data['returns']
        else:
            # Collect features from S&P 100
            rows = []
            labels_list = []
            returns_list = []
            tickers_used = SP100[:30]  # Use 30 for speed

            for i, t in enumerate(tickers_used):
                if progress_callback:
                    try:
                        progress_callback(i / len(tickers_used))
                    except Exception:
                        pass
                feat = _get_features(t)
                if feat is None:
                    continue
                # Get 1Y return as label
                try:
                    hist = yf.Ticker(t).history(period="1y")
                    ret_1y = (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) if len(hist) > 0 else 0
                except Exception:
                    ret_1y = 0

                # Quality label based on return
                if ret_1y > 0.20:
                    label = "EXCELENTE"
                elif ret_1y > 0.05:
                    label = "BUENA"
                elif ret_1y > -0.10:
                    label = "REGULAR"
                else:
                    label = "DEBIL"

                rows.append(feat)
                labels_list.append(label)
                returns_list.append(ret_1y)

            if len(rows) < 10:
                return False
            features_df = pd.DataFrame(rows).fillna(0)
            labels = labels_list
            returns = returns_list

            # Cache
            if HAS_JOBLIB:
                try:
                    joblib.dump({'features': features_df, 'labels': labels, 'returns': returns}, cache_file)
                except Exception:
                    pass

        # Train
        quality.train(features_df, labels)
        anomaly.train(features_df)
        scorer.train(features_df, returns)
        if lynch:
            lynch.train(features_df)
        return True
    except Exception:
        return False


def analyze_ticker(ticker):
    """Run all 4 models on a ticker. Returns dict."""
    try:
        quality, anomaly, scorer, lynch = get_models()
        if quality is None or not quality.trained:
            return None

        feat = _get_features(ticker)
        if feat is None:
            return None

        label, confidence = quality.predict(feat)
        anomalies = anomaly.detect(feat)
        smart_score = scorer.score(feat)
        importance = scorer.feature_importance()

        lynch_label, lynch_conf = "Unknown", 0
        if lynch and lynch.trained:
            lynch_label, lynch_conf = lynch.predict(feat)

        return {
            'quality_label': label,
            'quality_confidence': confidence,
            'anomalies': anomalies,
            'smart_score': smart_score,
            'feature_importance': importance,
            'lynch_profile': lynch_label,
            'lynch_confidence': lynch_conf,
            'features': feat,
        }
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# LOCAL NEURAL NETWORKS — No API, no limits
# ═══════════════════════════════════════════════════════════════

# ── XGBoost (optional upgrade for SmartScorer) ──
try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

# ── Prophet (time series forecasting) ──
try:
    from prophet import Prophet
    HAS_PROPHET = True
except ImportError:
    HAS_PROPHET = False

# ── GARCH (volatility forecasting) ──
try:
    from arch import arch_model
    HAS_GARCH = True
except ImportError:
    HAS_GARCH = False


def forecast_price(ticker: str, days: int = 30):
    """Prophet: project price forward N days. Returns DataFrame or None."""
    if not HAS_PROPHET:
        return None
    try:
        import yfinance as yf
        import pandas as pd
        hist = yf.download(ticker, period="2y", progress=False)
        if hist.empty:
            return None
        # Handle MultiIndex
        if isinstance(hist.columns, pd.MultiIndex):
            close = hist["Close"].iloc[:, 0]
        else:
            close = hist["Close"]
        close = close.dropna()
        df = pd.DataFrame({"ds": close.index.tz_localize(None), "y": close.values})
        m = Prophet(daily_seasonality=False, yearly_seasonality=True,
                    weekly_seasonality=True, changepoint_prior_scale=0.05)
        m.fit(df)
        future = m.make_future_dataframe(periods=days)
        forecast = m.predict(future)
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(days)
    except Exception:
        return None


def forecast_volatility(ticker: str, days: int = 30):
    """GARCH(1,1): forecast volatility. Returns dict or None."""
    if not HAS_GARCH:
        return None
    try:
        import yfinance as yf
        import pandas as pd
        hist = yf.download(ticker, period="2y", progress=False)
        if hist.empty:
            return None
        if isinstance(hist.columns, pd.MultiIndex):
            close = hist["Close"].iloc[:, 0]
        else:
            close = hist["Close"]
        returns = close.pct_change().dropna() * 100
        if len(returns) < 100:
            return None
        model = arch_model(returns, vol="Garch", p=1, q=1, mean="constant")
        res = model.fit(disp="off")
        fcast = res.forecast(horizon=days)
        current_vol = float(res.conditional_volatility.iloc[-1])
        forecast_vol = float(fcast.variance.iloc[-1].mean() ** 0.5)
        return {
            "current_vol_daily": current_vol,
            "forecast_vol_daily": forecast_vol,
            "current_vol_annual": current_vol * (252 ** 0.5),
            "forecast_vol_annual": forecast_vol * (252 ** 0.5),
        }
    except Exception:
        return None
