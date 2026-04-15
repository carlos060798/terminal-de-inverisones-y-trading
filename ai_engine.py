"""
ai_engine.py — Backward compatibility wrapper.
All AI logic has moved to ai_router.py + services/ + backends/.
This file re-exports all public functions so existing imports continue to work.
"""
try:
    from ai_router import (
        generate,
        analyze_stock,
        analyze_chart_image,
        analyze_portfolio,
        analyze_trade,
        generate_macro_insight,
        analyze_sentiment_finbert,
        get_available_providers,
        get_usage_dashboard,
        route,
        SYSTEM_FINANCE,
        SYSTEM_SUMMARY,
        SYSTEM_PORTFOLIO,
    )
    # Alias for backward compatibility
    ask_gemini = generate
except ImportError as e:
    # Fallback: if ai_router not available, provide minimal stubs
    import warnings
    warnings.warn(f"ai_router import failed: {e}. Using minimal stubs.")

    SYSTEM_FINANCE = "Eres un analista financiero."
    SYSTEM_SUMMARY = "Resume de inversión."
    SYSTEM_PORTFOLIO = "Analista de cartera."

    def generate(prompt, system=SYSTEM_FINANCE, max_tokens=1500):
        return None
    def analyze_stock(ticker, **kwargs):
        return None
    def analyze_chart_image(image_bytes, asset, **kwargs):
        return "AI Router no disponible"
    def analyze_portfolio(positions):
        return None
    def analyze_trade(ticker, trade_type, entry, **kwargs):
        return None
    def generate_macro_insight(**kwargs):
        return None
    def analyze_sentiment_finbert(headlines):
        return []
    def get_available_providers():
        return []
    def get_usage_dashboard():
        return []
    def route(task="text", prompt="", **kwargs):
        return ("Router no disponible", "none")
    def ask_gemini(prompt, **kwargs):
        return generate(prompt, **kwargs)
