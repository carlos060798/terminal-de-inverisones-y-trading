"""
agents/devil_advocate.py - Orquestador LangGraph (Pre-Mortem Analysis)
Usando llama-cpp-python para forzar revisiones de Kahneman Biases.
"""
from typing import Dict, TypedDict, Any
import json
import logging

try:
    from langgraph.graph import StateGraph, START, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

import openai

# Cliente genérico configurado para el servidor local de LM Studio
# LM Studio por defecto levanta su API en el puerto 1234
lm_client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

def get_ai_response(prompt: str, tokens: int = 150) -> str:
    """Invoca la IA local mediante LM Studio usando el protocolo OpenAI."""
    try:
        response = lm_client.chat.completions.create(
            model="local-model", # En LM Studio no importa el nombre exacto
            messages=[
                {"role": "system", "content": "Eres un prestigioso analista financiero y gestor de riesgos con estilo de Charlie Munger y Warren Buffett."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error conectando a LM Studio: {e}")
        return ""

# Definimos el Estado del LangGraph
class PreMortemState(TypedDict):
    ticker: str
    thesis: str
    score: int
    moats: list
    biases_detected: list
    fatal_flaws: list
    final_decision: str

def agent_analyzer(state: PreMortemState) -> Dict:
    """Nodo 1: Analiza la tesis para detectar sesgos cognitivos."""
    prompt = f"Analiza esta tesis del ticker {state['ticker']} y encuentra 1 sesgo de pensar (Confirmacion, Anclaje, etc):\\n{state['thesis']}"
    resp = get_ai_response(prompt, tokens=100)
    
    if not resp:
        # Fallback si LM Studio no está prendido
        resp = "Sesgo de Confirmacion (LM Studio no respondio, por favor asegurate de que el servidor este encendido)"
    
    return {"biases_detected": [resp]}

def devil_advocate(state: PreMortemState) -> Dict:
    """Nodo 2: Genera razones de fracaso extremo (Devil's Advocate)."""
    prompt = f"Actua como Abogado del Diablo. Dime de forma tajante y realista por qué esta inversion en {state['ticker']} va a fracasar catastróficamente.\\nTesis: {state['thesis']}"
    resp = get_ai_response(prompt, tokens=150)
    
    if not resp:
        resp = "Caída imprevista de márgenes (LM Studio apagado)."
        
    return {"fatal_flaws": [resp]}

def final_judgment(state: PreMortemState) -> Dict:
    """Nodo 3: Agrega los descubrimientos a la base de datos de Post-Mortem."""
    state["final_decision"] = "PENDIENTE_REVISION_HUMANA"
    return state

# Construcción de LangGraph
def build_pre_mortem_graph():
    if not HAS_LANGGRAPH:
        return None
    graph = StateGraph(PreMortemState)
    graph.add_node("analyzer", agent_analyzer)
    graph.add_node("devil", devil_advocate)
    graph.add_node("judgment", final_judgment)
    
    graph.add_edge(START, "analyzer")
    graph.add_edge("analyzer", "devil")
    graph.add_edge("devil", "judgment")
    graph.add_edge("judgment", END)
    
    return graph.compile()

def run_pre_mortem(ticker: str, thesis_text: str, current_score: int):
    """Función expuesta a Streamlit para arrancar el ciclo LangGraph."""
    graph = build_pre_mortem_graph()
    initial_state = {
        "ticker": ticker,
        "thesis": thesis_text,
        "score": current_score,
        "moats": [],
        "biases_detected": [],
        "fatal_flaws": [],
        "final_decision": ""
    }
    if graph is None:
        # Fallback manual pipeling simulation si LangGraph no está.
        s1 = agent_analyzer(initial_state)
        initial_state.update(s1)
        s2 = devil_advocate(initial_state)
        initial_state.update(s2)
        return final_judgment(initial_state)

    result_state = graph.invoke(initial_state)
    return result_state
