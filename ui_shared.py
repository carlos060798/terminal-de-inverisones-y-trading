"""
ui_shared.py - Shared UI utilities for Quantum Retail Terminal
Dark theme constants, formatters, KPI card builders.
"""
import pandas as pd

# Standard chart height constants
CHART_SM = 250
CHART_MD = 320
CHART_LG = 400

DARK = dict(
    paper_bgcolor="#000000",
    plot_bgcolor="#0a0a0a",
    font=dict(color="#94a3b8", size=12, family="Inter"),
    xaxis=dict(gridcolor="#1a1a1a", linecolor="#1a1a1a", zerolinecolor="#1a1a1a"),
    yaxis=dict(gridcolor="#1a1a1a", linecolor="#1a1a1a", zerolinecolor="#1a1a1a"),
    margin=dict(l=16, r=16, t=24, b=16),
)


def dark_layout(**overrides):
    """DARK theme con overrides. Elimina keys conflictivas antes de merge."""
    base = dict(DARK)
    for key in overrides:
        base.pop(key, None)
    base.update(overrides)
    return base

IDEAL = {
    "revenue_growth": {"min": 10,  "label": "Crec. Ingresos",  "unit": "%",  "higher": True},
    "profit_margin":  {"min": 15,  "label": "Margen Neto",      "unit": "%",  "higher": True},
    "roe":            {"min": 15,  "label": "ROE",              "unit": "%",  "higher": True},
    "current_ratio":  {"min": 1.5, "label": "Ratio Corriente",  "unit": "x",  "higher": True},
    "pe_ratio":       {"max": 25,  "label": "P/E Ratio",        "unit": "x",  "higher": False},
    "debt_equity":    {"max": 1.0, "label": "Deuda/Patrimonio", "unit": "x",  "higher": False},
}


def score(key, val):
    m = IDEAL.get(key)
    if not m or val is None:
        return None
    if m.get("higher", True):
        return val >= m["min"]
    return val <= m["max"]


def fmt(n, prefix="$", dec=2):
    import streamlit as st
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return "N/A"
    abs_n = abs(n)
    mode = st.session_state.get("notation_mode", "Compacto (M/B)")
    if mode == "Compacto (M/B)":
        if abs_n >= 1e12: return f"{prefix}{n/1e12:.{dec}f}T"
        if abs_n >= 1e9:  return f"{prefix}{n/1e9:.{dec}f}B"
        if abs_n >= 1e6:  return f"{prefix}{n/1e6:.{dec}f}M"
        if abs_n >= 1e3:  return f"{prefix}{n/1e3:.{dec}f}K"
    if prefix == "%":
        return f"{n:,.{dec}f}%"
    return f"{prefix}{n:,.{dec}f}"


def kpi(label, value, sub="", color="blue"):
    return f"""
    <div class='kpi-card'>
      <div class='kpi-label'>{label}</div>
      <div class='kpi-value'>{value}</div>
      <div class='kpi-sub kpi-{color}'>{sub}</div>
    </div>"""

def badge(text, status="ok"):
    """Render a premium badge (ok, error, warn)."""
    cls = f"status-{status}"
    return f"<span class='{cls}'>{text.upper()}</span>"

def latency_label(ms):
    """Render a colored latency label."""
    if ms == 0: return "<span style='color:#64748b'>-</span>"
    cls = "latency-low" if ms < 500 else "latency-high" if ms > 2000 else ""
    return f"<span class='{cls}'>{ms}ms</span>"
