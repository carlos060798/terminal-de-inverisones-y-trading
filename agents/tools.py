import valuation
import ml_engine
import pandas as pd
from typing import Dict, Any

def get_valuation_metrics(ticker: str) -> Dict[str, Any]:
    """Calcula el Fair Value, DCF y Margen de Seguridad de una acción."""
    try:
        res = valuation.compute_fair_values(ticker)
        return {
            "ticker": ticker,
            "fair_value": res.get("fair_value", 0),
            "upside_pct": res.get("upside_pct", 0),
            "graham_value": res.get("graham_value", 0),
            "dcf_value": res.get("dcf_value", 0),
            "success": True
        }
    except Exception as e:
        return {"ticker": ticker, "success": False, "error": str(e)}

def get_health_scores(ticker: str) -> Dict[str, Any]:
    """Calcula el Altman Z-Score (salud) y Piotroski F-Score (calidad) de una empresa."""
    try:
        res = valuation.compute_health_scores(ticker)
        return {
            "ticker": ticker,
            "z_score": res.get("z_score", 0),
            "f_score": res.get("f_score", 0),
            "bankruptcy_risk": "High" if res.get("z_score", 0) < 1.8 else "Safe",
            "success": True
        }
    except Exception as e:
        return {"ticker": ticker, "success": False, "error": str(e)}

def get_ml_insights(ticker: str) -> Dict[str, Any]:
    """Obtiene predicciones de Machine Learning sobre calidad y anomalías de una acción."""
    try:
        res = ml_engine.analyze_ticker(ticker)
        if res:
            return {
                "ticker": ticker,
                "quality_label": res.get("quality_label", "N/A"),
                "smart_score": res.get("smart_score", 50),
                "is_anomaly": res.get("is_anomaly", False),
                "success": True
            }
        return {"ticker": ticker, "success": False, "error": "No ML data available"}
    except Exception as e:
        return {"ticker": ticker, "success": False, "error": str(e)}

# Metadata for Function Calling (JSON Schema style)
TOOLS_METADATA = [
    {
        "name": "get_valuation_metrics",
        "description": "Calcula el valor intrínseco (Fair Value) y el potencial de subida (upside) usando DCF y Graham.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "El ticker de la acción (ej. AAPL, MSFT)"}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_health_scores",
        "description": "Evalúa el riesgo de quiebra (Altman Z-Score) y la salud contable (Piotroski F-Score).",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "El ticker de la acción"}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_ml_insights",
        "description": "Obtiene la puntuación inteligente y clasificación de calidad mediante modelos de Machine Learning.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "El ticker de la acción"}
            },
            "required": ["ticker"]
        }
    }
]

# Mapping for direct execution
TOOLS_MAP = {
    "get_valuation_metrics": get_valuation_metrics,
    "get_health_scores": get_health_scores,
    "get_ml_insights": get_ml_insights,
}
