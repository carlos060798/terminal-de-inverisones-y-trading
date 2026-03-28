import re

ML_PATH = r"c:\Users\usuario\Videos\dasboard\ml_engine.py"

with open(ML_PATH, "r", encoding="utf-8") as f:
    ml_content = f.read()

new_class = """
class PeterLynchClassifier:
    \"\"\"Random Forest to classify stocks into Peter Lynch profiles (Stalwart, Fast Grower, etc).\"\"\"
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
        \"\"\"Heuristically label the SP100 data to train the RF model.\"\"\"
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
"""

get_models_replacement = """
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
"""

# Replace models return tuple and instantiation code
ml_content = re.sub(r'# Singleton instances with Streamlit cache.*?return _quality, _anomaly, _scorer\n',
    new_class + "\n" + get_models_replacement, ml_content, flags=re.DOTALL)

# Update train_models
ml_content = ml_content.replace(
    'quality, anomaly, scorer = get_models()',
    'quality, anomaly, scorer, lynch = get_models()'
)
ml_content = ml_content.replace(
    'scorer.train(features_df, returns)',
    'scorer.train(features_df, returns)\n        if lynch:\n            lynch.train(features_df)'
)

# Update analyze_ticker
ml_content = ml_content.replace(
    'def analyze_ticker(ticker):\n    \"\"\"Run all 3 models',
    'def analyze_ticker(ticker):\n    \"\"\"Run all 4 models'
)
ml_content = ml_content.replace(
    'quality, anomaly, scorer = get_models()',
    'quality, anomaly, scorer, lynch = get_models()'
)

# Insert the lynch prediction into analyze_ticker
lynch_pred_code = """
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
"""
ml_content = re.sub(
    r'return \{\s+\'quality_label\': label.*?\'features\': feat,\s+\}',
    lynch_pred_code.strip(), ml_content, flags=re.DOTALL
)

with open(ML_PATH, "w", encoding="utf-8") as f:
    f.write(ml_content)
