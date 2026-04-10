"""Vision Service — Chart and image analysis with 9 vision-capable providers."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from balancer import pick, record, PROVIDERS

# ---------------------------------------------------------------------------
# Vision provider chain (ordered by preference)
# ---------------------------------------------------------------------------
VISION_CHAIN = [
    "openai-4o", "gemini-flash", "gemini-1.5", "groq-vision",
    "or-qwen-vl", "openai-4o-mini", "hf-llama-vision", "hf-qwen-vl", "hf-florence",
]

SYSTEM_CHART = """Eres un analista tecnico profesional de mercados financieros.
Responde SIEMPRE en espanol. Se conciso y especifico con niveles de precio."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _get_backend(provider_id):
    """Dynamically import and return the correct backend module."""
    backend_name = PROVIDERS[provider_id]["backend"]
    mod = __import__(f"backends.{backend_name}_backend", fromlist=["call"])
    return mod


def _build_prompt(asset, timeframe="", analysis_type="Tecnico Completo",
                  patterns_text=""):
    """Build the analysis prompt based on parameters."""
    tf_context = f"\nTimeframe del grafico: {timeframe}" if timeframe else ""
    patterns_ctx = (
        f"\nPatrones detectados automaticamente: {patterns_text}"
        if patterns_text else ""
    )

    type_instructions = {
        "Tecnico Completo": """Proporciona en espanol:
1. **Tendencia principal** (alcista/bajista/lateral) y fuerza
2. **Soportes y Resistencias** clave visibles
3. **Patrones chartistas** identificados
4. **Senales tecnicas** (divergencias, cruces, volumen)
5. **Plan de Trading**: Entrada, Stop Loss, Take Profit (2 targets), R:R
6. **Senal final**: COMPRA / VENTA / NEUTRAL con confianza (%)""",

        "Soportes y Resistencias": """Enfocate SOLO en:
1. **Soportes** — niveles exactos de precio, fuerza (fuerte/medio/debil), cuantas veces testeado
2. **Resistencias** — niveles exactos, fuerza, relevancia historica
3. **Zonas de liquidez** o acumulacion/distribucion
4. **Nivel critico** mas importante a vigilar""",

        "Patrones Chartistas": """Enfocate SOLO en:
1. **Patrones clasicos**: H&S, doble techo/suelo, triangulos, banderas, cunyas
2. **Patrones de velas**: doji, hammer, engulfing, morning/evening star
3. **Estado del patron**: en formacion, confirmado, fallido
4. **Objetivo de precio** implicado por cada patron""",

        "Accion de Precio": """Enfocate SOLO en:
1. **Estructura de mercado**: HH/HL (alcista) o LH/LL (bajista)
2. **Order blocks** y zonas de oferta/demanda
3. **Liquidez**: barridos, trampas de liquidez, stops hunt
4. **Momentum**: impulso vs correccion, agotamiento
5. **Bias direccional** con nivel de invalidacion""",
    }

    instructions = type_instructions.get(
        analysis_type, type_instructions["Tecnico Completo"]
    )

    return (
        f"Eres un analista tecnico profesional. "
        f"Analiza este grafico de {asset}.{tf_context}{patterns_ctx}\n\n"
        f"{instructions}\n\n"
        f"Se conciso y especifico con niveles de precio."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def analyze_chart(image_bytes, asset, timeframe="",
                  analysis_type="Tecnico Completo", mime="image/png",
                  patterns_text=""):
    """Analyze a chart image using the vision provider chain, or a forced provider if set."""
    import streamlit as st
    prompt = _build_prompt(asset, timeframe, analysis_type, patterns_text)

    # ── AI BYPASS LOGIC ──────────────────────────────────────────────────────
    forced_id = st.session_state.get("force_llm", "Auto-Balanceador")
    active_chain = VISION_CHAIN
    
    if forced_id != "Auto-Balanceador" and forced_id in PROVIDERS:
        # Solo forzar si el modelo elegido soporta vision
        if PROVIDERS[forced_id].get("vision"):
            active_chain = [forced_id] + [p for p in VISION_CHAIN if p != forced_id]

    errors = []
    for pid in active_chain:
        provider = PROVIDERS.get(pid)
        if not provider or not provider.get("vision"):
            continue
        try:
            backend = _get_backend(pid)
            model = provider["model"]
            result = backend.call(model, prompt, SYSTEM_CHART, 1500,
                                  image_bytes, mime)
            if result:
                record(pid)
                return (result, pid)
        except Exception as e:
            errors.append(f"{pid}: {str(e)[:80]}")
            continue

    return (
        "Todos los providers de vision fallaron.\n" + "\n".join(errors),
        "none",
    )
