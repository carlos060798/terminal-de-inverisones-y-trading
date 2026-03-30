"""
sentiment.py - Analista de Sentimiento Local (FinBERT)
Procesa noticias financieras en milisegundos usando transformers y la GPU/CPU local.
"""
try:
    from transformers import pipeline
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

_classifier = None

def get_finbert():
    global _classifier
    if not HAS_TRANSFORMERS:
        return None
    if _classifier is None:
        # Intenta usar CUDA (GPU RTX 3050 Ti) si existe, de lo contrario CPU
        device = 0 if torch.cuda.is_available() else -1
        try:
            _classifier = pipeline("sentiment-analysis", model="ProsusAI/finbert", device=device)
        except Exception:
            _classifier = None
    return _classifier

def analyze_sentiment_finbert(headlines: list) -> list:
    """
    Recibe lista de titulares y devuelve lista de métricas de sentimiento:
    [{'headline': '...', 'label': 'positive/negative/neutral', 'score': 0.99}, ...]
    """
    if not headlines:
        return []
        
    model = get_finbert()
    if not model:
        return [{"headline": h, "label": "neutral", "score": 0.5, "error": "FinBERT no instalado"} for h in headlines]
        
    results = []
    try:
        preds = model(headlines)
        for h, p in zip(headlines, preds):
            results.append({
                "headline": h,
                "label": p["label"],
                "score": round(p["score"], 3)
            })
        return results
    except Exception as e:
        print(f"Error procesando FinBERT: {e}")
        return []

def aggregate_sentiment(headlines: list) -> dict:
    """Calcula un score macro de los titulares (bullish/bearish ratio)."""
    analyzed = analyze_sentiment_finbert(headlines)
    if not analyzed or "error" in analyzed[0]:
        return {"bullish": 0, "bearish": 0, "neutral": len(headlines), "avg_score": 0.5, "details": analyzed if analyzed else []}
        
    bull = sum(1 for a in analyzed if a['label'] == 'positive')
    bear = sum(1 for a in analyzed if a['label'] == 'negative')
    neut = sum(1 for a in analyzed if a['label'] == 'neutral')
    
    # Score de -1 (Bearish max) a 1 (Bullish max)
    score_sum = sum((a['score'] if a['label'] == 'positive' else (-a['score'] if a['label'] == 'negative' else 0)) for a in analyzed)
    avg_score = score_sum / len(headlines) if headlines else 0
    
    return {
        "bullish": bull,
        "bearish": bear,
        "neutral": neut,
        "avg_score": round(avg_score, 2),
        "details": analyzed
    }
