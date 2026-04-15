"""Text Service — Fundamental analysis, portfolio, trades, macro insights."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from balancer import pick, record, PROVIDERS

# ---------------------------------------------------------------------------
# Specialized Provider Chains (Quantum Distribution v8.7)
# ---------------------------------------------------------------------------
# 1. ANALYSIS_CHAIN: Máxima calidad de razonamiento y lógica financiera
ANALYSIS_CHAIN  = ["deepseek-reasoner", "openai-4o", "or-deepseek", "groq-llama"]

# 2. CONTEXT_CHAIN: Máximo tamaño de ventana de contexto (PDFs, Macro, Historiales largos)
CONTEXT_CHAIN   = ["gemini-flash", "openai-4o", "groq-llama"]

# 3. VELOCITY_CHAIN: Respuesta instantánea para resúmenes y chats rápidos
VELOCITY_CHAIN  = ["groq-llama", "openai-4o-mini", "deepseek-chat", "or-qwen"]

# 4. VISION_CHAIN: Especializados en análisis de imágenes y gráficos financieros
VISION_CHAIN    = ["openai-4o", "gemini-flash"]

# Fallback universal
TEXT_CHAIN = ANALYSIS_CHAIN + VELOCITY_CHAIN
REASONING_CHAIN = ["deepseek-reasoner", "or-deepseek", "openai-4o"]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
SYSTEM_FINANCE = "Analista financiero senior. Responde SIEMPRE en español. Conciso. Sin disclaimers."

SYSTEM_SUMMARY = "Resumen ejecutivo de inversión: tesis, riesgos, catalizadores, veredicto. Español. Bullets directos."

SYSTEM_PORTFOLIO = "Gestor de cartera institucional. Analiza diversificación, riesgo, rebalanceo. Español."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _get_backend(provider_id):
    """Dynamically import and return the correct backend module."""
    backend_name = PROVIDERS[provider_id]["backend"]
    mod = __import__(f"backends.{backend_name}_backend", fromlist=["call"])
    return mod


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------
def generate_consensus(prompt, system=SYSTEM_FINANCE, max_tokens=1500, top_n=3):
    """Generate text by calling N providers in parallel and returning a combined view."""
    from concurrent.futures import ThreadPoolExecutor
    import streamlit as st
    
    # Select N available providers from different backends if possible
    pool = ["openai-4o", "gemini-flash", "groq-llama", "deepseek-chat", "or-qwen"]
    available = [p for p in pool if pick([p])]
    candidates = available[:top_n]
    
    results = []
    
    def _call(pid):
        try:
            backend = _get_backend(pid)
            model = PROVIDERS[pid]["model"]
            return backend.call(model, prompt, system, max_tokens)
        except:
            return None

    with ThreadPoolExecutor(max_workers=top_n) as executor:
        responses = list(executor.map(_call, candidates))
    
    valid_responses = [r for r in responses if r]
    if not valid_responses:
        return generate(prompt, system, max_tokens) # Fallback to serial
    
    # Logic to "sum" or "merge" - for now, we show the best or a concatenated view
    # In a real consensus, we'd ask a 4th LLM to merge them, but for performance:
    combined = f"### Análasis por Consenso ({len(valid_responses)} modelos)\n\n"
    for i, res in enumerate(valid_responses):
        provider_name = candidates[i]
        combined += f"**Opinion {i+1} ({provider_name})**:\n{res[:500]}...\n\n"
    
    return (combined, "consensus-engine")

def generate(prompt, system=SYSTEM_FINANCE, max_tokens=1500, tools=None, chain_type="text"):
    """Generate text using a specialized chain or the universal fallback."""
    import streamlit as st
    
    # Map chain types
    chains = {
        "analysis": ANALYSIS_CHAIN,
        "context": CONTEXT_CHAIN,
        "velocity": VELOCITY_CHAIN,
        "vision": VISION_CHAIN,
        "text": TEXT_CHAIN
    }
    
    # ── AI BYPASS LOGIC ──────────────────────────────────────────────────────
    forced_id = st.session_state.get("force_llm", "Auto-Balanceador")
    active_chain = chains.get(chain_type, TEXT_CHAIN)
    
    if forced_id != "Auto-Balanceador" and forced_id in PROVIDERS:
        # Prepend the forced ID to ensure it's tried first
        active_chain = [forced_id] + [p for p in active_chain if p != forced_id]

    errors = []
    
    # Check if we should use consensus (parallel) for this request
    # Consensus is only manually invoked now to save tokens
    if chain_type == "consensus" and forced_id == "Auto-Balanceador" and not tools:
        try:
            res, pid = generate_consensus(prompt, system, max_tokens)
            if res: return (res, pid)
        except:
            pass

    for pid in active_chain:
        provider = PROVIDERS.get(pid)
        if not provider:
            continue
        try:
            # Check availability at runtime (secrets might have changed)
            from balancer import is_available
            if not is_available(pid):
                continue
                
            backend = _get_backend(pid)
            model = provider["model"]
            
            # Use a slightly more robust call pattern
            result = backend.call(model, prompt, system, max_tokens, tools=tools)
            
            if result and not result.startswith("Error:"):
                record(pid)
                return (result, pid)
            elif result and result.startswith("Error:"):
                errors.append(f"{pid}: {result}")
        except Exception as e:
            errors.append(f"{pid}: {str(e)[:80]}")
            continue

    # Final error reporting ONLY if all models failed
    if errors:
        st.error(f"❌ Agotados todos los modelos de la cadena '{chain_type}'. Errores: {'; '.join(errors[:3])}")
    return (None, "none")


# ---------------------------------------------------------------------------
# High-level analysis functions
# ---------------------------------------------------------------------------
def analyze_stock(ticker, price=None, pe=None, roe=None, margin=None,
                  revenue_growth=None, debt_equity=None, fair_value=None,
                  quality_score=None, sector=None):
    """Generate an executive investment summary for a stock.

    Returns tuple[str | None, str].
    """
    data_parts = [f"Ticker: {ticker}"]
    if price:
        data_parts.append(f"Precio actual: ${price:,.2f}")
    if pe:
        data_parts.append(f"P/E Ratio: {pe:.1f}")
    if roe:
        data_parts.append(f"ROE: {roe:.1f}%")
    if margin:
        data_parts.append(f"Margen Neto: {margin:.1f}%")
    if revenue_growth:
        data_parts.append(f"Crecimiento Ingresos: {revenue_growth:.1f}%")
    if debt_equity:
        data_parts.append(f"Deuda/Equity: {debt_equity:.2f}")
    if fair_value:
        data_parts.append(f"Fair Value estimado: ${fair_value:,.2f}")
    if quality_score is not None:
        data_parts.append(f"Quality Score Buffett: {quality_score}/100")
    if sector:
        data_parts.append(f"Sector: {sector}")

    data_str = "\n".join(data_parts)
    prompt = f"Resume esta acción:\n{data_str}\nIncluye: Resumen, Fortalezas, Riesgos, Veredicto y Catalizadores."

    return generate(prompt, SYSTEM_SUMMARY, chain_type="analysis")


def analyze_portfolio(positions):
    """Analyze a portfolio of positions.

    Parameters
    ----------
    positions : list[dict]
        Each dict has keys: ticker, shares, avg_cost, current_price, pnl_pct, sector.

    Returns tuple[str | None, str].
    """
    if not positions:
        return (None, "none")

    pos_text = ""
    for p in positions:
        pos_text += f"- {p.get('ticker', '?')}: {p.get('shares', 0):.0f} acciones, "
        pos_text += f"costo ${p.get('avg_cost', 0):,.2f}, "
        pos_text += f"actual ${p.get('current_price', 0):,.2f}, "
        pos_text += f"P&L {p.get('pnl_pct', 0):+.1f}%, "
        pos_text += f"sector: {p.get('sector', '?')}\n"

    prompt = f"Analiza cartera:\n{pos_text}\nEvalúa: Diversificación, Riesgo, Rebalanceo, Oportunidades, Veredicto (1-10)."

    return generate(prompt, SYSTEM_PORTFOLIO, chain_type="analysis")


def analyze_trade(ticker, trade_type, entry, exit_price=None, pnl=None,
                  strategy=None, user_query=None):
    """Generate a post-mortem analysis of a trade.

    Returns tuple[str | None, str].
    """
    req_q = f"PREGUNTA DEL USUARIO: {user_query}" if user_query else "Analiza: Evaluación, Lección y Perspectiva a corto plazo."
    prompt = f"TICKER: {ticker} | TIPO: {trade_type} | ENTRADA: ${entry:,.4f} | SALIDA: ${exit_price if exit_price else 'ABIERTO'} | PNL: {pnl if pnl else ''} | EST: {strategy if strategy else ''}\n{req_q}"

    return generate(prompt, SYSTEM_FINANCE, max_tokens=800, chain_type="velocity")


def generate_macro_insight(vix=None, yield_10y=None, sp500_ytd=None, user_query=None):
    """Generate a macro-economic insight.

    Returns tuple[str | None, str].
    """
    data_parts = []
    if vix:
        data_parts.append(f"VIX: {vix:.1f}")
    if yield_10y:
        data_parts.append(f"Treasury 10Y: {yield_10y:.2f}%")
    if sp500_ytd:
        data_parts.append(f"S&P 500 YTD: {sp500_ytd:+.1f}%")

    req_q = f"ENFOQUE: {user_query}" if user_query else "Genera un análisis macro breve: Fase del ciclo, Implicación retail, Sectores, Riesgo."
    prompt = f"MACRO CONTEXT:\n{chr(10).join(data_parts)}\n{req_q}"

    return generate(prompt, SYSTEM_FINANCE, max_tokens=800, chain_type="context")

# ── QUANTUM AI ASSISTANT ───────────────────────────────────────────────────────
def answer_financial_question(query: str, context_data: str, ticker: str = None) -> tuple[str, str]:
    """
    Responde una pregunta financiera de usuario usando el mejor modelo.
    Context Data encapsula toda la info de la UI/intel_engine/noticias listos para ser consumidos.
    """
    if ticker:
        sys_prompt = f"Quantum AI Assistant. Explica el contexto de {ticker} breve."
    else:
        sys_prompt = "Quantum AI Assistant. Experto macro. Sé conciso."

    final_prompt = f"CONTEXT:\n{context_data}\n\nUSER:\n{query}"
    
    return generate(final_prompt, sys_prompt, max_tokens=800, chain_type="velocity")
