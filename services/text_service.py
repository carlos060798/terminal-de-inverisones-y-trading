"""Text Service — Fundamental analysis, portfolio, trades, macro insights."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from balancer import pick, record, PROVIDERS

# ---------------------------------------------------------------------------
# Provider chains
# ---------------------------------------------------------------------------
TEXT_CHAIN = ["groq-llama", "deepseek-chat", "gemini-flash", "or-qwen", "or-deepseek"]
REASONING_CHAIN = ["deepseek-reasoner", "deepseek-chat", "gemini-flash", "or-deepseek"]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
SYSTEM_FINANCE = """Eres un analista financiero senior especializado en inversiones.
Responde SIEMPRE en español. Sé conciso, profesional y directo.
Usa datos concretos cuando estén disponibles. Estructura tu respuesta con secciones claras.
No uses disclaimers legales extensos."""

SYSTEM_SUMMARY = """Eres un analista financiero que genera resúmenes ejecutivos de inversión.
Responde SIEMPRE en español. Formato: bullet points concisos.
Incluye: tesis principal, riesgos clave, catalizadores, y veredicto (Comprar/Mantener/Evitar)."""

SYSTEM_PORTFOLIO = """Eres un gestor de cartera institucional que analiza portfolios.
Responde SIEMPRE en español. Analiza diversificación, riesgo, y oportunidades.
Da recomendaciones concretas y accionables."""


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
def generate(prompt, system=SYSTEM_FINANCE, max_tokens=1500):
    """Generate text using the TEXT_CHAIN fallback sequence.

    Returns
    -------
    tuple[str | None, str]
        (generated_text, provider_id_used)
    """
    errors = []
    for pid in TEXT_CHAIN:
        provider = PROVIDERS.get(pid)
        if not provider:
            continue
        try:
            backend = _get_backend(pid)
            model = provider["model"]
            result = backend.call(model, prompt, system, max_tokens)
            if result:
                record(pid)
                return (result, pid)
        except Exception as e:
            errors.append(f"{pid}: {str(e)[:80]}")
            continue

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

    prompt = f"""Analiza esta acción y genera un resumen de inversión ejecutivo:

{data_str}

Estructura tu respuesta así:
**Resumen**: 2-3 oraciones sobre la empresa
**Fortalezas**: 3 bullet points
**Riesgos**: 3 bullet points
**Veredicto**: Comprar / Mantener / Evitar + precio objetivo si es posible
**Catalizadores**: Eventos próximos que podrían mover el precio"""

    return generate(prompt, SYSTEM_SUMMARY)


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

    prompt = f"""Analiza esta cartera de inversión:

{pos_text}

Evalúa:
**Diversificación**: ¿Está bien diversificada por sector? ¿Concentración excesiva?
**Riesgo**: ¿Cuál es el nivel de riesgo general? ¿Posiciones problemáticas?
**Rebalanceo**: ¿Qué ajustes recomendarías?
**Oportunidades**: ¿Qué sectores o posiciones podrían mejorar la cartera?
**Veredicto General**: Calificación del portfolio (1-10) y resumen en 2 oraciones."""

    return generate(prompt, SYSTEM_PORTFOLIO)


def analyze_trade(ticker, trade_type, entry, exit_price=None, pnl=None,
                  strategy=None):
    """Generate a post-mortem analysis of a trade.

    Returns tuple[str | None, str].
    """
    prompt = f"""Analiza esta operación de trading:

Ticker: {ticker}
Tipo: {trade_type}
Entrada: ${entry:,.4f}
{"Salida: $" + f"{exit_price:,.4f}" if exit_price else "Posición ABIERTA"}
{"P&L: $" + f"{pnl:+,.2f}" if pnl else ""}
{"Estrategia: " + strategy if strategy else ""}

Genera un análisis post-mortem breve:
**Evaluación**: ¿Fue una buena entrada? ¿El timing fue correcto?
**Lección**: ¿Qué se puede aprender de esta operación?
**Perspectiva**: ¿Qué esperar de este ticker a corto plazo?"""

    return generate(prompt, SYSTEM_FINANCE, max_tokens=800)


def generate_macro_insight(vix=None, yield_10y=None, sp500_ytd=None):
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

    prompt = f"""Dado el contexto macro actual:
{chr(10).join(data_parts)}

Genera un análisis macro breve (máximo 5 oraciones):
- ¿En qué fase del ciclo económico estamos?
- ¿Qué implica para un inversor retail?
- ¿Sectores defensivos o cíclicos? ¿Renta fija o variable?
- ¿Riesgo principal a vigilar?"""

    return generate(prompt, SYSTEM_FINANCE, max_tokens=600)
