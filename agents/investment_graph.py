import os
from typing import Annotated, Dict, List, TypedDict, Union
from langgraph.graph import StateGraph, END
from adapters.execution_engine import ExecutionEngine
import valuation
import ml_engine
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State Definition
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    ticker: str
    query: str
    messages: List[Dict[str, str]]
    # Data components
    fundamental_data: Dict
    technical_analysis: Dict
    risk_assessment: Dict
    final_thesis: str
    next_step: str

# ---------------------------------------------------------------------------
# Nodes (The Agents)
# ---------------------------------------------------------------------------

def extractor_node(state: AgentState) -> Dict:
    """Agent A: Focuses on the 'Data Bunker' (SEC, yfinance, FRED)."""
    ticker = state.get("ticker", "UNKNOWN")
    print(f"  [Grafo] Nodo Extractor: Buscando datos para {ticker}...")
    
    engine = ExecutionEngine()
    sec_res = engine.fetch_one("sec_edgar", ticker=ticker, form_type="10-K")
    yf_res = engine.fetch_one("yfinance", ticker=ticker)
    fred_res = engine.fetch_one("fred", series_id="GS10")
    # 4. Fetch FMP Core Ratios (Fast)
    fmp_res = engine.fetch_one("fmp", ticker=ticker)
    
    print(f"  [Grafo] Extractor finalizado.")
    return {
        "fundamental_data": {
            "sec": sec_res.data if sec_res and sec_res.success else {},
            "yfinance": yf_res.data if yf_res and yf_res.success else {},
            "macro": fred_res.data if fred_res and fred_res.success else {},
            "fmp": fmp_res.data if fmp_res and fmp_res.success else {}
        },
        "next_step": "analyst"
    }

def analyst_node(state: AgentState) -> Dict:
    """Agent B: Focuses on Valuation (DCF, Multiples)."""
    ticker = state.get("ticker", "UNKNOWN")
    print(f"  [Grafo] Nodo Analista: Valorando {ticker}...")
    
    try:
        fair_values = valuation.compute_fair_values(ticker)
        health = valuation.compute_health_scores(ticker)
        print(f"  [Grafo] Analista finalizado (Fair Value: {fair_values.get('fair_value', 0)})")
        return {
            "technical_analysis": {
                "fair_values": fair_values if fair_values else {},
                "health_scores": health if health else {}
            },
            "next_step": "critic"
        }
    except Exception as e:
        print(f"  [Grafo] Analista error: {e}")
        return {"technical_analysis": {"error": str(e)}, "next_step": "critic"}

def critic_node(state: AgentState) -> Dict:
    """Agent C: Risk Critic & Sentiment."""
    ticker = state.get("ticker", "UNKNOWN")
    print(f"  [Grafo] Nodo Crítico: Evaluando riesgos para {ticker}...")
    
    try:
        ml_res = ml_engine.analyze_ticker(ticker)
        print(f"  [Grafo] Crítico finalizado.")
        return {
            "risk_assessment": {
                "ml_insights": ml_res if ml_res else {},
                "sentiment": "Neutral (simulated)"
            },
            "next_step": "summarizer"
        }
    except Exception as e:
        print(f"  [Grafo] Crítico error: {e}")
        return {"risk_assessment": {"error": str(e)}, "next_step": "summarizer"}

def summarizer_node(state: AgentState) -> Dict:
    """Agent D: The Thesis Generator."""
    ticker = state.get("ticker", "UNKNOWN")
    print(f"  [Grafo] Nodo Summarizer: Generando tesis para {ticker}...")
    
    tech = state.get("technical_analysis", {})
    if not tech: tech = {}
    
    risk = state.get("risk_assessment", {})
    if not risk: risk = {}
    
    fv_data = tech.get("fair_values", {})
    if not fv_data: fv_data = {}
    
    health_data = tech.get("health_scores", {})
    if not health_data: health_data = {}
    
    ml_data = risk.get("ml_insights", {})
    if not ml_data: ml_data = {}

    upside = fv_data.get("upside_pct", 0)
    z_score = health_data.get("z_score", 0)
    
    thesis = f"# 📝 Tesis de Inversión: {ticker}\n\n"
    thesis += f"## 💎 Valoración\n"
    thesis += f"- **Upside Estimado**: {upside:+.2f}%\n"
    thesis += f"- **Z-Score (Salud)**: {z_score:.2f}\n\n"
    thesis += f"## ⚠️ Riesgos y ML\n"
    thesis += f"- **Calidad ML**: {ml_data.get('quality_label', 'N/A')}\n"
    
    print(f"  [Grafo] Summarizer finalizado.")
    return {"final_thesis": thesis}

# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("extractor", extractor_node)
workflow.add_node("analyst", analyst_node)
workflow.add_node("critic", critic_node)
workflow.add_node("summarizer", summarizer_node)

# Add Edges
workflow.set_entry_point("extractor")
workflow.add_edge("extractor", "analyst")
workflow.add_edge("analyst", "critic")
workflow.add_edge("critic", "summarizer")
workflow.add_edge("summarizer", END)

# Compile
app = workflow.compile()

def run_investment_task(ticker: str, query: str = ""):
    """Public entry point for the agentic workflow."""
    print(f"--- Iniciando Grafo para {ticker} ---")
    initial_state = {
        "ticker": ticker,
        "query": query,
        "messages": [],
        "fundamental_data": {},
        "technical_analysis": {},
        "risk_assessment": {},
        "final_thesis": "",
        "next_step": ""
    }
    try:
        final_state = app.invoke(initial_state)
        print(f"--- Grafo Finalizado para {ticker} ---")
        return final_state
    except Exception as e:
        print(f"❌ Error en app.invoke: {e}")
        return {}
