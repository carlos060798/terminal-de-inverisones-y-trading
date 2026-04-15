"""AI Request Balancer -- Distributes requests across providers to avoid quota exhaustion."""
import streamlit as st
from datetime import date

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
PROVIDERS = {
    # ── PREMIUM (Pago) ────────────────────────────────────────────────────────
    "openai-4o":         {"backend": "openai",      "model": "gpt-4o",                          "vision": True,  "daily_limit": 500,   "name": "GPT-4o"},
    "openai-4o-mini":    {"backend": "openai",      "model": "gpt-4o-mini",                     "vision": True,  "daily_limit": 2000,  "name": "GPT-4o Mini"},
    "deepseek-reasoner": {"backend": "deepseek",    "model": "deepseek-reasoner",               "vision": False, "daily_limit": 500,   "name": "DeepSeek R1"},
    "deepseek-chat":     {"backend": "deepseek",    "model": "deepseek-chat",                   "vision": False, "daily_limit": 1000,  "name": "DeepSeek V3"},
    # ── GRATUITOS ALTA CUOTA ──────────────────────────────────────────────────
    "gemini-flash":      {"backend": "google",      "model": "gemini-2.5-flash-preview-04-17",  "vision": True,  "daily_limit": 1000,  "name": "Gemini 2.5 Flash"},
    "groq-llama":        {"backend": "groq",        "model": "llama-3.3-70b-versatile",         "vision": False, "daily_limit": 1000,  "name": "Llama 3.3 70B"},
    # ── GRATUITOS FALLBACK (OpenRouter) ──────────────────────────────────────
    "or-qwen":           {"backend": "openrouter",  "model": "qwen/qwen-2.5-72b-instruct:free", "vision": False, "daily_limit": 200,   "name": "Qwen 72B Free"},
    "or-deepseek":       {"backend": "openrouter",  "model": "deepseek/deepseek-r1:free",        "vision": False, "daily_limit": 200,   "name": "DeepSeek R1 Free"},
    # ── ESPECIALIZADO FINANZAS ────────────────────────────────────────────────
    "hf-finbert":        {"backend": "hf",          "model": "ProsusAI/finbert",                "vision": False, "daily_limit": 10000, "name": "FinBERT"},
}

# Map backend names to the API key each one requires
_BACKEND_KEYS = {
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "hf": "HF_TOKEN",
    "local": None,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_secret(name: str) -> str:
    try:
        val = st.secrets.get(name)
        if val:
            return val
    except Exception:
        pass
    return __import__('os').environ.get(name, "")


def _get_usage() -> dict:
    """Return the daily usage dict from session state, resetting if the date changed."""
    today = date.today().isoformat()

    if "ai_usage" not in st.session_state or st.session_state.get("ai_usage_date") != today:
        st.session_state["ai_usage"] = {pid: 0 for pid in PROVIDERS}
        st.session_state["ai_usage_date"] = today

    usage = st.session_state["ai_usage"]
    # Ensure any new providers added after session start are present
    for pid in PROVIDERS:
        if pid not in usage:
            usage[pid] = 0

    return usage


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record(provider_id: str) -> None:
    """Increment the usage counter for a provider."""
    usage = _get_usage()
    usage[provider_id] = usage.get(provider_id, 0) + 1


def pick(chain: list[str]) -> str | None:
    """Pick the provider with the lowest usage percentage from *chain*.

    Providers that have exceeded 95 % of their daily limit are skipped.
    Returns the provider id or ``None`` if every candidate is exhausted.
    """
    usage = _get_usage()
    best_id = None
    best_pct = 1.0  # 100 %

    for pid in chain:
        info = PROVIDERS.get(pid)
        if info is None:
            continue
        if not is_available(pid):
            continue
        limit = info["daily_limit"]
        used = usage.get(pid, 0)
        pct = used / limit if limit > 0 else 1.0
        if pct > 0.95:
            continue
        if pct < best_pct:
            best_pct = pct
            best_id = pid

    return best_id


def is_available(provider_id: str) -> bool:
    """Check whether the required API key for a provider is configured."""
    info = PROVIDERS.get(provider_id)
    if info is None:
        return False
    key_name = _BACKEND_KEYS.get(info["backend"], "MISSING_KEY")
    if key_name is None:
        return True # Local backends always 'available' if chosen
    return bool(_get_secret(key_name))


def dashboard_data() -> list[dict]:
    """Return status information for every registered provider.

    Each entry contains: id, name, backend, model, vision, limit, used, pct, available.
    """
    usage = _get_usage()
    rows = []
    for pid, info in PROVIDERS.items():
        limit = info["daily_limit"]
        used = usage.get(pid, 0)
        pct = round(used / limit * 100, 1) if limit > 0 else 0.0
        rows.append({
            "id": pid,
            "name": info["name"],
            "backend": info["backend"],
            "model": info["model"],
            "vision": info["vision"],
            "limit": limit,
            "used": used,
            "pct": pct,
            "available": is_available(pid),
        })
    return rows
