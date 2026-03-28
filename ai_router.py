"""
ai_router.py — Central AI Router with load balancing across 15 models.

Maintains full backward compatibility with the ai_engine.py interface.
All existing code can import from here (or from ai_engine.py which will
redirect to this module).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import vision_service, text_service, sentiment_service, table_service
from balancer import dashboard_data, PROVIDERS, is_available
from agents.tools import TOOLS_METADATA
from agents.investment_graph import run_investment_task

# ---------------------------------------------------------------------------
# Re-export system prompts for backward compatibility
# ---------------------------------------------------------------------------
SYSTEM_FINANCE = text_service.SYSTEM_FINANCE
SYSTEM_SUMMARY = text_service.SYSTEM_SUMMARY
SYSTEM_PORTFOLIO = text_service.SYSTEM_PORTFOLIO


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _detect_mime(file_name):
    """Detect MIME type from a file name/extension.

    .jpg / .jpeg -> image/jpeg
    .webp        -> image/webp
    default      -> image/png
    """
    name = (file_name or "").lower()
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image/jpeg"
    if name.endswith(".webp"):
        return "image/webp"
    return "image/png"


# ---------------------------------------------------------------------------
# Backward-compatible public API
# ---------------------------------------------------------------------------
def generate(prompt, system=SYSTEM_FINANCE, max_tokens=1500, use_tools=True):
    """Generate text via the text provider chain, with tools enabled by default.

    Returns
    -------
    str | None
        The generated text, or ``None`` if all providers failed.
    """
    tools = TOOLS_METADATA if use_tools else None
    text, _pid = text_service.generate(prompt, system, max_tokens, tools=tools)
    return text


def analyze_stock(ticker, price=None, pe=None, roe=None, margin=None,
                  revenue_growth=None, debt_equity=None, fair_value=None,
                  quality_score=None, sector=None):
    """Generate an AI investment summary for a stock.

    Returns str | None.
    """
    text, _pid = text_service.analyze_stock(
        ticker, price, pe, roe, margin, revenue_growth,
        debt_equity, fair_value, quality_score, sector,
    )
    return text


def analyze_chart_image(image_bytes, asset, patterns_text="", timeframe="",
                        analysis_type="Tecnico Completo", file_name=""):
    """Analyze a chart image using vision providers.

    Returns str (analysis text; never None).
    """
    mime = _detect_mime(file_name)
    text, _pid = vision_service.analyze_chart(
        image_bytes, asset, timeframe, analysis_type, mime, patterns_text,
    )
    return text


def analyze_portfolio(positions):
    """Analyze a portfolio of positions.

    Returns str | None.
    """
    text, _pid = text_service.analyze_portfolio(positions)
    return text


def analyze_trade(ticker, trade_type, entry, exit_price=None, pnl=None,
                  strategy=None, user_query=None):
    """Post-mortem analysis of a trade.

    Returns str | None.
    """
    text, _pid = text_service.analyze_trade(
        ticker, trade_type, entry, exit_price, pnl, strategy, user_query=user_query
    )
    return text


def generate_macro_insight(vix=None, yield_10y=None, sp500_ytd=None, user_query=None):
    """Generate a macro-economic insight.

    Returns str | None.
    """
    text, _pid = text_service.generate_macro_insight(vix, yield_10y, sp500_ytd, user_query=user_query)
    return text


def analyze_sentiment_finbert(headlines):
    """Sentiment analysis via FinBERT.

    Returns list[dict] with keys ``label`` and ``score``.
    """
    return sentiment_service.analyze_headlines(headlines)


def get_available_providers():
    """Return a deduplicated list of available provider display names.

    Example: ["Gemini", "Groq", "OpenAI", "DeepSeek", ...]
    """
    seen = set()
    names = []
    for pid, info in PROVIDERS.items():
        if is_available(pid):
            display = info.get("name", pid)
            if display not in seen:
                seen.add(display)
                names.append(display)
    return names


def get_usage_dashboard():
    """Return usage/health data for all providers.

    Returns list[dict] from ``balancer.dashboard_data()``.
    """
    return dashboard_data()


# ---------------------------------------------------------------------------
# Direct router for new code
# ---------------------------------------------------------------------------
def route(task="text", prompt="", system="", max_tokens=1500,
          image_bytes=None, mime="image/png"):
    """Unified routing entry point for new code.

    Parameters
    ----------
    task : str
        One of ``"text"``, ``"vision"``, ``"reasoning"``, ``"sentiment"``.
    prompt : str
        The user prompt / question.
    system : str
        System prompt override (uses default per task if empty).
    max_tokens : int
        Maximum tokens in the response.
    image_bytes : bytes | None
        Raw image data (required when task="vision").
    mime : str
        MIME type for the image.

    Returns
    -------
    tuple[str, str]
        (result_text, provider_id_used)
    """
    if task == "vision":
        if not image_bytes:
            return ("No image provided for vision task.", "none")
        return vision_service.analyze_chart(
            image_bytes, asset=prompt, mime=mime,
        )

    if task == "sentiment":
        results = sentiment_service.analyze_headlines(
            [prompt] if isinstance(prompt, str) else prompt
        )
        if results:
            summary = "; ".join(
                f"{r['label']} ({r['score']:.0%})" for r in results
            )
            return (summary, "hf-finbert")
        return ("No sentiment results.", "none")

    if task == "reasoning":
        # Use the reasoning chain via text_service internals
        original_chain = text_service.TEXT_CHAIN
        try:
            text_service.TEXT_CHAIN = text_service.REASONING_CHAIN
            return text_service.generate(
                prompt, system or SYSTEM_FINANCE, max_tokens,
            )
        finally:
            text_service.TEXT_CHAIN = original_chain

    # Default: text with tools
    return text_service.generate(
        prompt, system or SYSTEM_FINANCE, max_tokens, tools=TOOLS_METADATA
    )

def run_agentic_analysis(ticker: str, query: str = ""):
    """Run the autonomous LangGraph agent for a complex ticker analysis."""
    try:
        result = run_investment_task(ticker, query)
        return result.get("final_thesis", "No se pudo generar la tesis.")
    except Exception as e:
        return f"Error en el agente autónomo: {e}"
