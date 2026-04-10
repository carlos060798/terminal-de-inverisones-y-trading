"""Sentiment Service — FinBERT-based financial sentiment analysis (Local & Cloud)."""
import streamlit as st
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

FINBERT_MODEL = "ProsusAI/finbert"

@st.cache_resource
def load_finbert():
    """Carga el modelo FinBERT localmente para inferencia rápida a coste cero."""
    if not HAS_TRANSFORMERS:
        return None
    try:
        tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
        model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL)
        return pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
    except Exception as e:
        st.error(f"Error al cargar FinBERT local: {e}")
        return None

def analyze_headlines(headlines):
    """
    Analiza una lista de titulares. 
    Intenta usar el motor local (Sprint 2) y cae a la API de HF si falla.
    """
    if not headlines:
        return []
    
    # 1. Intento Local (Preferencia Sprint 2)
    clf = load_finbert()
    if clf:
        try:
            results = clf(headlines)
            # Normalizar etiquetas de FinBERT (positive, negative, neutral) a mi formato
            return [{"label": r['label'].lower(), "score": r['score']} for r in results]
        except Exception:
            pass # Si falla local, intentar nube
            
    # 2. Fallback a Nube (API)
    try:
        from backends import hf_backend
        return hf_backend.sentiment(headlines)
    except Exception:
        return []

def classify_news(text):
    """Clasifica un único texto."""
    results = analyze_headlines([text])
    return results[0] if results else {"label": "neutral", "score": 0.5}
