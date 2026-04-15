"""
services/debate_service.py — Multi-Agent Bull vs Bear Debate Engine
Simulates a debate between a Bull Analyst and a Bear Analyst, synthesized by a Judge.
"""
from ai_router import generate

SYSTEM_BULL = """Eres un analista financiero especializado en detectar oportunidades 'Growth' y 'Value'. 
Tu misión es defender a ultranza el CASO BULL de la acción. 
Busca catalizadores positivos, ventajas competitivas (Moat), solidez financiera y subvaloración. 
Sé convincente, profesional y optimista basado en datos. Responde en ESPAÑOL."""

SYSTEM_BEAR = """Eres un analista financiero escéptico y gestor de riesgos. 
Tu misión es defender a ultranza el CASO BEAR de la acción. 
Busca riesgos ocultos, competencia feroz, sobrevaloración, debilidades en el balance y vientos de cola macro negativos. 
Sé crítico, directo y pesimista basado en datos. Responde en ESPAÑOL."""

SYSTEM_JUDGE = """Eres un Comité de Inversiones institucional. 
Tu misión es recibir un Caso Bull y un Caso Bear de una acción y sintetizar un veredicto imparcial.
Debes equilibrar ambos argumentos y dar una conclusión lógica basada en probabilidades.
Responde en ESPAÑOL."""

def run_bull_bear_debate(ticker, data_context=""):
    """
    Runs a 3-agent debate.
    data_context: string with current fundamental/technical data.
    """
    
    # 1. Bull Agent
    prompt_bull = f"Genera el mejor CASO BULL posible para {ticker}. Contexto de datos:\n{data_context}"
    bull_case = generate(prompt_bull, system=SYSTEM_BULL)
    
    # 2. Bear Agent
    prompt_bear = f"Genera el mejor CASO BEAR posible para {ticker}. Contexto de datos:\n{data_context}"
    bear_case = generate(prompt_bear, system=SYSTEM_BEAR)
    
    # 3. Judge Synthesis
    prompt_judge = f"""Sintetiza un veredicto para {ticker} basado en estos dos casos:
    
    BULL CASE:
    {bull_case}
    
    BEAR CASE:
    {bear_case}
    
    Proporciona un resumen ejecutivo, los puntos de inflexión clave y un veredicto final (Comprar/Mantener/Evitar)."""
    
    verdict = generate(prompt_judge, system=SYSTEM_JUDGE)
    
    return {
        "bull": bull_case,
        "bear": bear_case,
        "verdict": verdict
    }
