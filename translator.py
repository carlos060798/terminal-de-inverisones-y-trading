"""
translator.py — Financial English→Spanish translator
Uses deep-translator (Google Translate, free) for long text.
Uses dictionary for short terms (ratings, labels).
"""
import re

try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False


def _google_translate(text: str) -> str:
    """Translate text using Google Translate (free, no API key)."""
    if not HAS_TRANSLATOR or not text or len(text.strip()) < 10:
        return text
    try:
        # Google Translate has a 5000 char limit per request
        if len(text) <= 4900:
            return GoogleTranslator(source='en', target='es').translate(text)
        # Split long texts into chunks
        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current = ""
        for s in sentences:
            if len(current) + len(s) + 1 > 4900:
                if current:
                    chunks.append(current)
                current = s
            else:
                current = (current + " " + s).strip() if current else s
        if current:
            chunks.append(current)
        translated = []
        for chunk in chunks:
            t = GoogleTranslator(source='en', target='es').translate(chunk)
            translated.append(t or chunk)
        return " ".join(translated)
    except Exception:
        return text

# ── TERM DICTIONARY (exact replacements, case-insensitive matching) ──────────
TERMS = {
    # Analyst ratings
    "Strong Buy": "Compra Fuerte",
    "Buy": "Comprar",
    "Overweight": "Sobreponderar",
    "Outperform": "Superar",
    "Hold": "Mantener",
    "Neutral": "Neutral",
    "Equal-Weight": "Igual Ponderación",
    "Underweight": "Infraponderar",
    "Underperform": "Bajo Rendimiento",
    "Sell": "Vender",
    "Strong Sell": "Venta Fuerte",
    "Market Perform": "Rendimiento de Mercado",
    "Sector Perform": "Rendimiento del Sector",
    "Sector Outperform": "Supera al Sector",
    "Peer Perform": "Rendimiento de Pares",

    # Financial statement labels
    "Revenue": "Ingresos",
    "Total Revenue": "Ingresos Totales",
    "Net Income": "Beneficio Neto",
    "Net Income to Stockholders": "Beneficio Neto para Accionistas",
    "Operating Income": "Beneficio Operativo",
    "Gross Profit": "Beneficio Bruto",
    "EBITDA": "EBITDA",
    "Diluted EPS": "BPA Diluido",
    "Total Assets": "Activos Totales",
    "Total Equity": "Patrimonio Total",
    "Total Debt": "Deuda Total",
    "Total Liabilities": "Pasivos Totales",
    "Total Current Assets": "Activos Corrientes",
    "Total Current Liabilities": "Pasivos Corrientes",
    "Cash from Operations": "Flujo de Operaciones",
    "Cash from Investing": "Flujo de Inversión",
    "Cash from Financing": "Flujo de Financiación",
    "Levered Free Cash Flow": "Flujo de Caja Libre Apalancado",
    "Free Cash Flow": "Flujo de Caja Libre",
    "Shares Outstanding": "Acciones en Circulación",
    "Income Statement": "Estado de Resultados",
    "Balance Sheet": "Balance General",
    "Cash Flow Statement": "Estado de Flujo de Caja",

    # Valuation
    "Fair Value": "Valor Justo",
    "Capitalization": "Capitalización",
    "Market Cap": "Capitalización de Mercado",
    "Price / Book": "Precio / Valor Libro",
    "EV / Revenue": "VE / Ingresos",
    "EV / EBITDA": "VE / EBITDA",
    "EV / FCF": "VE / FCL",
    "FCF Yield": "Rendimiento FCL",
    "Div. Yield": "Rendimiento Dividendo",
    "Dividend Yield": "Rendimiento por Dividendo",
    "P/E Ratio": "Ratio P/B",
    "PEG Ratio": "Ratio PEG",
    "Reporting Date": "Fecha de Reporte",
    "Period Ending": "Fin del Período",

    # Key indicators
    "Stock Price": "Precio de Acción",
    "52-Week Range": "Rango 52 Semanas",
    "Book / Share": "Valor Libro / Acción",
    "Revenue Forecast": "Pronóstico de Ingresos",
    "1-Year Change": "Cambio 1 Año",
    "Next Earnings": "Próximos Resultados",
    "EPS Actual": "BPA Real",
    "EPS Estimate": "BPA Estimado",
    "EPS Revisions": "Revisiones BPA",
    "Div. Growth Streak": "Racha Crec. Dividendo",

    # Sections
    "Executive Summary": "Resumen Ejecutivo",
    "Key Indicators": "Indicadores Clave",
    "Analyst EPS Forecasts": "Proyecciones BPA de Analistas",
    "Latest Ratings": "Últimas Calificaciones",
    "Pro Tips": "Consejos Pro",
    "SWOT Analysis": "Análisis FODA",
    "Strengths": "Fortalezas",
    "Weaknesses": "Debilidades",
    "Opportunities": "Oportunidades",
    "Threats": "Amenazas",
    "Bull Case": "Caso Alcista",
    "Bear Case": "Caso Bajista",
    "Technical Summary": "Resumen Técnico",
    "Peer Benchmarks": "Comparación con Pares",
    "Latest Insights": "Últimos Insights",
    "Additional Insights": "Insights Adicionales",
    "Momentum": "Momentum",
}

# ── PHRASE PATTERNS for Pro Tips & SWOT sentences ────────────────────────────
PHRASES = {
    # Pro Tips common patterns
    "Has a perfect Piotroski Score of": "Tiene un Piotroski Score perfecto de",
    "Has raised its dividend for": "Ha aumentado su dividendo durante",
    "consecutive years": "años consecutivos",
    "Impressive gross profit margins": "Márgenes de beneficio bruto impresionantes",
    "Trading at a low P/E ratio relative to near-term earnings growth": "Cotiza con un P/E bajo relativo al crecimiento de beneficios a corto plazo",
    "Significant return over the last week": "Retorno significativo en la última semana",
    "Prominent player in the": "Actor destacado en la industria de",
    "industry": "industria",
    "Has maintained dividend payments for": "Ha mantenido pagos de dividendos durante",
    "Analysts predict the company will be profitable this year": "Los analistas predicen que la compañía será rentable este año",
    "Profitable over the last twelve months": "Rentable en los últimos doce meses",
    "High return over the last decade": "Alto retorno en la última década",
    "analysts have revised their earnings downwards for the upcoming period": "analistas han revisado sus beneficios a la baja para el próximo período",
    "analysts have revised their earnings upwards": "analistas han revisado sus beneficios al alza",
    "Trading at a high EBITDA valuation multiple": "Cotiza con un múltiplo de valoración EBITDA alto",
    "Trading at a high Price / Book multiple": "Cotiza con un múltiplo Precio/Valor Libro alto",
    "Price has fallen significantly over the last three months": "El precio ha caído significativamente en los últimos tres meses",
    "Stock has taken a big hit over the last six months": "La acción ha sufrido una gran caída en los últimos seis meses",
    "Stock has taken a big hit over the last week": "La acción ha sufrido una gran caída en la última semana",
    "Liquid assets exceed short-term obligations": "Los activos líquidos superan las obligaciones a corto plazo",
    "Short-term obligations exceed liquid assets": "Las obligaciones a corto plazo superan los activos líquidos",
    "Operates with a moderate level of debt": "Opera con un nivel moderado de deuda",
    "Operates with a high level of debt": "Opera con un nivel alto de deuda",
    "Operates with a low level of debt": "Opera con un nivel bajo de deuda",
    "Cash flows can sufficiently cover interest payments": "Los flujos de caja cubren suficientemente los pagos de intereses",
    "Pays a significant dividend to shareholders": "Paga un dividendo significativo a los accionistas",
    "Pays a reliable dividend to shareholders": "Paga un dividendo confiable a los accionistas",
    "Does not pay a dividend to shareholders": "No paga dividendo a los accionistas",
    "Moderate dividend growth track record": "Historial moderado de crecimiento de dividendos",
    "Strong dividend growth track record": "Historial fuerte de crecimiento de dividendos",
    "Revenue is forecast to grow": "Se pronostica crecimiento de ingresos",
    "Earnings are forecast to grow": "Se pronostica crecimiento de beneficios",
    "Earnings have declined over the past year": "Los beneficios han disminuido en el último año",
    "Revenue growth has slowed": "El crecimiento de ingresos se ha desacelerado",
    "Highly volatile stock price": "Precio de la acción altamente volátil",
    "Strong past financial performance": "Fuerte desempeño financiero pasado",
    "Weak past financial performance": "Desempeño financiero pasado débil",
    "Good value based on earnings": "Buen valor basado en beneficios",
    "Good value based on free cash flow": "Buen valor basado en flujo de caja libre",
    "Not good value based on free cash flow": "No es buen valor basado en flujo de caja libre",
    "Management has been effectively allocating capital": "La gerencia ha estado asignando capital de manera efectiva",
    "Trading near its 52-week high": "Cotiza cerca de su máximo de 52 semanas",
    "Trading near its 52-week low": "Cotiza cerca de su mínimo de 52 semanas",
    "Positive free cash flow": "Flujo de caja libre positivo",
    "Negative free cash flow": "Flujo de caja libre negativo",
    "Strong earnings growth": "Fuerte crecimiento de beneficios",
    "Stable earnings growth": "Crecimiento estable de beneficios",
    "More volatile than the broader market": "Más volátil que el mercado general",
    "Less volatile than the broader market": "Menos volátil que el mercado general",

    # SWOT common phrases
    "The company": "La compañía",
    "the company": "la compañía",
    "The stock": "La acción",
    "the stock": "la acción",
    "market share": "cuota de mercado",
    "competitive advantage": "ventaja competitiva",
    "competitive moat": "foso competitivo",
    "recurring revenue": "ingresos recurrentes",
    "subscription model": "modelo de suscripción",
    "profit margins": "márgenes de beneficio",
    "gross margins": "márgenes brutos",
    "operating margins": "márgenes operativos",
    "net margins": "márgenes netos",
    "revenue growth": "crecimiento de ingresos",
    "earnings growth": "crecimiento de beneficios",
    "year-over-year": "interanual",
    "quarter-over-quarter": "trimestre a trimestre",
    "fiscal year": "año fiscal",
    "earnings per share": "beneficio por acción",
    "price-to-earnings": "precio-beneficio",
    "debt-to-equity": "deuda-patrimonio",
    "return on equity": "retorno sobre patrimonio",
    "return on assets": "retorno sobre activos",
    "return on investment": "retorno de inversión",
    "free cash flow": "flujo de caja libre",
    "cash flow": "flujo de caja",
    "operating income": "beneficio operativo",
    "net income": "beneficio neto",
    "total revenue": "ingresos totales",
    "shareholder value": "valor para el accionista",
    "dividend payments": "pagos de dividendos",
    "dividend growth": "crecimiento de dividendos",
    "share buyback": "recompra de acciones",
    "stock repurchase": "recompra de acciones",
    "balance sheet": "balance general",
    "income statement": "estado de resultados",
    "cash flow statement": "estado de flujo de caja",
    "interest rates": "tasas de interés",
    "inflation": "inflación",
    "supply chain": "cadena de suministro",
    "cloud computing": "computación en la nube",
    "artificial intelligence": "inteligencia artificial",
    "machine learning": "aprendizaje automático",
    "customer base": "base de clientes",
    "customer acquisition": "adquisición de clientes",
    "brand recognition": "reconocimiento de marca",
    "brand loyalty": "lealtad de marca",
    "regulatory environment": "entorno regulatorio",
    "regulatory risk": "riesgo regulatorio",
    "regulatory compliance": "cumplimiento regulatorio",
    "headwinds": "vientos en contra",
    "tailwinds": "vientos a favor",
    "upside potential": "potencial alcista",
    "downside risk": "riesgo bajista",
    "growth prospects": "perspectivas de crecimiento",
    "growth trajectory": "trayectoria de crecimiento",
    "strong demand": "demanda fuerte",
    "weak demand": "demanda débil",
    "cost efficiency": "eficiencia de costos",
    "cost reduction": "reducción de costos",
    "economies of scale": "economías de escala",
    "switching costs": "costos de cambio",
    "barriers to entry": "barreras de entrada",
    "intellectual property": "propiedad intelectual",
    "research and development": "investigación y desarrollo",
    "R&D": "I+D",
    "However": "Sin embargo",
    "Moreover": "Además",
    "Furthermore": "Además",
    "In addition": "Adicionalmente",
    "Despite": "A pesar de",
    "Although": "Aunque",
    "significantly": "significativamente",
    "approximately": "aproximadamente",
    "consecutive": "consecutivos",
    "substantial": "sustancial",
    "sustainable": "sostenible",
    "robust": "robusto",
    "resilient": "resiliente",
    "volatile": "volátil",
    "undervalued": "infravalorada",
    "overvalued": "sobrevalorada",
    "outperform": "superar el rendimiento",
    "underperform": "rendimiento inferior",
    "strong buy": "compra fuerte",
    "Software": "Software",
}


def translate_text(text: str, use_google: bool = True) -> str:
    """Translate financial text from English to Spanish.

    For long text (>50 chars): uses Google Translate if available.
    For short text: uses dictionary matching.
    """
    if not text or not isinstance(text, str):
        return text or ""

    # Long text → Google Translate (free)
    if use_google and len(text) > 50:
        return _google_translate(text)

    # Short text → dictionary
    result = text
    sorted_phrases = sorted(PHRASES.items(), key=lambda x: len(x[0]), reverse=True)
    for eng, esp in sorted_phrases:
        pattern = re.compile(re.escape(eng), re.IGNORECASE)
        result = pattern.sub(esp, result)
    return result


def translate_rating(rating: str) -> str:
    """Translate analyst rating (exact match)."""
    if not rating:
        return rating
    # Try exact match first
    for eng, esp in TERMS.items():
        if rating.strip().lower() == eng.lower():
            return esp
    return rating


def translate_list(items: list, use_google: bool = True) -> list:
    """Translate a list of text items (pro tips, SWOT bullets)."""
    if not items:
        return items
    return [translate_text(item, use_google=use_google) for item in items]


def translate_dict_keys(d: dict, key_map: dict = None) -> dict:
    """Translate dictionary keys using TERMS or custom map."""
    if not d:
        return d
    if key_map is None:
        key_map = TERMS
    result = {}
    for k, v in d.items():
        new_key = key_map.get(k, k)
        result[new_key] = v
    return result


def translate_parsed_data(parsed: dict) -> dict:
    """Translate all translatable fields in a parsed PDF result.

    Modifies in-place and returns the dict.
    """
    if not parsed:
        return parsed

    # Executive Summary
    if parsed.get("executive_summary"):
        parsed["executive_summary"] = translate_text(parsed["executive_summary"])

    # Key indicators - executive summary inside
    ki = parsed.get("key_indicators", {})
    if ki.get("executive_summary"):
        ki["executive_summary"] = translate_text(ki["executive_summary"])

    # SWOT
    swot = parsed.get("swot", {})
    for key in ("strengths", "weaknesses", "opportunities", "threats"):
        if swot.get(key):
            swot[key] = translate_list(swot[key])

    # Pro Tips
    if parsed.get("pro_tips"):
        parsed["pro_tips"] = translate_list(parsed["pro_tips"])

    # Valuation pro tips
    val = parsed.get("valuation_data", {})
    if val.get("pro_tips"):
        val["pro_tips"] = translate_list(val["pro_tips"])

    # Analyst ratings
    analyst = parsed.get("analyst", {})
    if analyst.get("ratings"):
        for r in analyst["ratings"]:
            if r.get("rating"):
                r["rating"] = translate_rating(r["rating"])

    # Insights
    insights = parsed.get("insights", {})
    for key in ("bull_case", "bear_case", "latest_insights"):
        if insights.get(key):
            insights[key] = translate_list(insights[key])

    # Technical summary
    momentum = parsed.get("momentum_peers", {})
    if momentum.get("technical_summary"):
        momentum["technical_summary"] = translate_rating(momentum["technical_summary"])

    return parsed
