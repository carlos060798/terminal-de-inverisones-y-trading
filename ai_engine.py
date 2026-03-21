"""
ai_engine.py — Multi-provider AI engine with fallback chain.
Providers: Google Gemini (primary) → Groq (fast) → OpenRouter (DeepSeek R1)
All free tiers, no cost.
"""
import streamlit as st
import json
from typing import Optional

# ---------------------------------------------------------------------------
# Provider imports (all optional)
# ---------------------------------------------------------------------------
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    from openai import OpenAI
    HAS_OPENROUTER = True
except ImportError:
    HAS_OPENROUTER = False


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
SYSTEM_FINANCE = """Eres un analista financiero senior especializado en inversiones.
Responde SIEMPRE en español. Sé conciso, profesional y directo.
Usa datos concretos cuando estén disponibles. Estructura tu respuesta con secciones claras.
No uses disclaimers legales extensos — el usuario sabe que esto no es asesoría financiera."""

SYSTEM_SUMMARY = """Eres un analista financiero que genera resúmenes ejecutivos de inversión.
Responde SIEMPRE en español. Formato: bullet points concisos.
Incluye: tesis principal, riesgos clave, catalizadores, y veredicto (Comprar/Mantener/Evitar).
Sé directo y usa números cuando estén disponibles."""

SYSTEM_PORTFOLIO = """Eres un gestor de cartera institucional que analiza portfolios.
Responde SIEMPRE en español. Analiza diversificación, riesgo, y oportunidades.
Da recomendaciones concretas y accionables."""


# ---------------------------------------------------------------------------
# Provider clients (cached)
# ---------------------------------------------------------------------------
@st.cache_resource
def _get_gemini():
    """Initialize Gemini client."""
    if not HAS_GEMINI:
        return None
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            genai.configure(api_key=key)
            return genai.GenerativeModel("gemini-2.0-flash")
    except Exception:
        pass
    return None


@st.cache_resource
def _get_groq():
    """Initialize Groq client."""
    if not HAS_GROQ:
        return None
    try:
        key = st.secrets.get("GROQ_API_KEY")
        if key:
            return Groq(api_key=key)
    except Exception:
        pass
    return None


@st.cache_resource
def _get_openrouter():
    """Initialize OpenRouter client (OpenAI-compatible)."""
    if not HAS_OPENROUTER:
        return None
    try:
        key = st.secrets.get("OPENROUTER_API_KEY")
        if key:
            return OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=key,
            )
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Core generation with fallback
# ---------------------------------------------------------------------------
def generate(prompt: str, system: str = SYSTEM_FINANCE, max_tokens: int = 1500) -> Optional[str]:
    """Generate text using fallback chain: Gemini → Groq → OpenRouter.

    Returns the generated text or None if all providers fail.
    """
    # Try Gemini first (best quality, generous free tier)
    result = _try_gemini(prompt, system, max_tokens)
    if result:
        return result

    # Try Groq (fastest, LLaMA 3.3 70B)
    result = _try_groq(prompt, system, max_tokens)
    if result:
        return result

    # Try OpenRouter (DeepSeek R1 free)
    result = _try_openrouter(prompt, system, max_tokens)
    if result:
        return result

    return None


def _try_gemini(prompt: str, system: str, max_tokens: int) -> Optional[str]:
    """Try Google Gemini."""
    model = _get_gemini()
    if not model:
        return None
    try:
        full_prompt = f"{system}\n\n{prompt}"
        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.3,
            ),
        )
        if response and response.text:
            return response.text.strip()
    except Exception:
        pass
    return None


def _try_groq(prompt: str, system: str, max_tokens: int) -> Optional[str]:
    """Try Groq (LLaMA 3.3 70B)."""
    client = _get_groq()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        if response and response.choices:
            return response.choices[0].message.content.strip()
    except Exception:
        pass
    return None


def _try_openrouter(prompt: str, system: str, max_tokens: int) -> Optional[str]:
    """Try OpenRouter (DeepSeek R1 free)."""
    client = _get_openrouter()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        if response and response.choices:
            text = response.choices[0].message.content.strip()
            # DeepSeek R1 sometimes wraps reasoning in <think> tags — remove them
            if "<think>" in text:
                import re
                text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            return text
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# High-level analysis functions
# ---------------------------------------------------------------------------
def analyze_stock(ticker: str, price: float = None, pe: float = None,
                  roe: float = None, margin: float = None,
                  revenue_growth: float = None, debt_equity: float = None,
                  fair_value: float = None, quality_score: int = None,
                  sector: str = None) -> Optional[str]:
    """Generate AI analysis summary for a stock."""
    data_parts = [f"Ticker: {ticker}"]
    if price: data_parts.append(f"Precio actual: ${price:,.2f}")
    if pe: data_parts.append(f"P/E Ratio: {pe:.1f}")
    if roe: data_parts.append(f"ROE: {roe:.1f}%")
    if margin: data_parts.append(f"Margen Neto: {margin:.1f}%")
    if revenue_growth: data_parts.append(f"Crecimiento Ingresos: {revenue_growth:.1f}%")
    if debt_equity: data_parts.append(f"Deuda/Equity: {debt_equity:.2f}")
    if fair_value: data_parts.append(f"Fair Value estimado: ${fair_value:,.2f}")
    if quality_score is not None: data_parts.append(f"Quality Score Buffett: {quality_score}/100")
    if sector: data_parts.append(f"Sector: {sector}")

    data_str = "\n".join(data_parts)

    prompt = f"""Analiza esta acción y genera un resumen de inversión ejecutivo:

{data_str}

Estructura tu respuesta así:
**📊 Resumen**: 2-3 oraciones sobre la empresa
**✅ Fortalezas**: 3 bullet points
**⚠️ Riesgos**: 3 bullet points
**🎯 Veredicto**: Comprar / Mantener / Evitar + precio objetivo si es posible
**💡 Catalizadores**: Eventos próximos que podrían mover el precio"""

    return generate(prompt, SYSTEM_SUMMARY)


def analyze_portfolio(positions: list) -> Optional[str]:
    """Generate AI analysis of a portfolio.

    positions: list of dicts with keys: ticker, shares, avg_cost, current_price, pnl_pct, sector
    """
    if not positions:
        return None

    pos_text = ""
    for p in positions:
        pos_text += f"- {p.get('ticker','?')}: {p.get('shares',0):.0f} acciones, "
        pos_text += f"costo ${p.get('avg_cost',0):,.2f}, "
        pos_text += f"actual ${p.get('current_price',0):,.2f}, "
        pos_text += f"P&L {p.get('pnl_pct',0):+.1f}%, "
        pos_text += f"sector: {p.get('sector','?')}\n"

    prompt = f"""Analiza esta cartera de inversión:

{pos_text}

Evalúa:
**📊 Diversificación**: ¿Está bien diversificada por sector? ¿Concentración excesiva?
**⚡ Riesgo**: ¿Cuál es el nivel de riesgo general? ¿Posiciones problemáticas?
**🔄 Rebalanceo**: ¿Qué ajustes recomendarías?
**💰 Oportunidades**: ¿Qué sectores o posiciones podrían mejorar la cartera?
**🎯 Veredicto General**: Calificación del portfolio (1-10) y resumen en 2 oraciones."""

    return generate(prompt, SYSTEM_PORTFOLIO)


def analyze_trade(ticker: str, trade_type: str, entry: float, exit_price: float = None,
                  pnl: float = None, strategy: str = None) -> Optional[str]:
    """Generate AI post-mortem analysis of a trade."""
    prompt = f"""Analiza esta operación de trading:

Ticker: {ticker}
Tipo: {trade_type}
Entrada: ${entry:,.4f}
{"Salida: $" + f"{exit_price:,.4f}" if exit_price else "Posición ABIERTA"}
{"P&L: $" + f"{pnl:+,.2f}" if pnl else ""}
{"Estrategia: " + strategy if strategy else ""}

Genera un análisis post-mortem breve:
**📊 Evaluación**: ¿Fue una buena entrada? ¿El timing fue correcto?
**📚 Lección**: ¿Qué se puede aprender de esta operación?
**🔮 Perspectiva**: ¿Qué esperar de este ticker a corto plazo?"""

    return generate(prompt, SYSTEM_FINANCE, max_tokens=800)


def generate_macro_insight(vix: float = None, yield_10y: float = None,
                           sp500_ytd: float = None) -> Optional[str]:
    """Generate AI macro economic insight."""
    data_parts = []
    if vix: data_parts.append(f"VIX: {vix:.1f}")
    if yield_10y: data_parts.append(f"Treasury 10Y: {yield_10y:.2f}%")
    if sp500_ytd: data_parts.append(f"S&P 500 YTD: {sp500_ytd:+.1f}%")

    prompt = f"""Dado el contexto macro actual:
{chr(10).join(data_parts)}

Genera un análisis macro breve (máximo 5 oraciones):
- ¿En qué fase del ciclo económico estamos?
- ¿Qué implica para un inversor retail?
- ¿Sectores defensivos o cíclicos? ¿Renta fija o variable?
- ¿Riesgo principal a vigilar?"""

    return generate(prompt, SYSTEM_FINANCE, max_tokens=600)


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------
def get_available_providers() -> list:
    """Return list of available AI providers."""
    providers = []
    if _get_gemini():
        providers.append("Gemini")
    if _get_groq():
        providers.append("Groq")
    if _get_openrouter():
        providers.append("OpenRouter")
    return providers
