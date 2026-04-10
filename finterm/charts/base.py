"""
finterm/charts/base.py
Global configuration, theme, and colors for the charting module.
"""
import plotly.io as pio
import plotly.graph_objects as go

# ── PALETA DE COLORES (Bloomberg / Institutional Dark) ──
COLORS = {
    "bg_main": "#0a0e1a",      # Fondo principal
    "bg_panel": "#111827",     # Fondo de paneles
    "bg_card": "#1f2937",      # Fondo de tarjetas
    "text_main": "#f9fafb",    # Texto principal
    "text_sec": "#9ca3af",     # Texto secundario
    "bull": "#00d4aa",         # Verde alcista (Cian/Verde)
    "bear": "#ff4d6d",         # Rojo bajista
    "neutral": "#fbbf24",      # Ámbar/Amarillo
    "accent": "#3b82f6",       # Azul acento
    "purple": "#8b5cf6",       # Morado acento
    "grid": "#1f2937",         # Líneas de cuadrícula
    "overlay": "rgba(255, 255, 255, 0.05)"
}

# ── CONFIGURACIÓN GLOBAL DE PLOTLY ──
def get_finterm_theme():
    """Returns a custom Plotly template for institutional charts."""
    theme = go.layout.Template()
    
    theme.layout = go.Layout(
        paper_bgcolor=COLORS["bg_main"],
        plot_bgcolor=COLORS["bg_main"],
        font=dict(family="Inter, Roboto, sans-serif", size=12, color=COLORS["text_main"]),
        xaxis=dict(
            gridcolor=COLORS["grid"],
            linecolor=COLORS["grid"],
            zerolinecolor=COLORS["grid"],
            tickfont=dict(size=10, color=COLORS["text_sec"]),
            showgrid=True,
        ),
        yaxis=dict(
            gridcolor=COLORS["grid"],
            linecolor=COLORS["grid"],
            zerolinecolor=COLORS["grid"],
            tickfont=dict(size=10, color=COLORS["text_sec"]),
            showgrid=True,
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=COLORS["text_sec"]),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=COLORS["bg_card"],
            font_size=12,
            font_family="JetBrains Mono, monospace"
        )
    )
    return theme

# Apply theme globally for the session
pio.templates["finterm_dark"] = get_finterm_theme()
pio.templates.default = "finterm_dark"

def apply_theme(fig):
    """Applies the finterm theme to a given plotly figure."""
    fig.update_layout(template="finterm_dark")
    return fig

def export_as_html(fig, filename):
    """Exports a figure as a standalone HTML file."""
    fig.write_html(filename, full_html=True, include_plotlyjs="cdn")

def export_as_png(fig, filename, width=1200, height=800):
    """Exports a figure as a high-resolution PNG using kaleido."""
    fig.write_image(filename, width=width, height=height, scale=2)

# Chart Constants
DEFAULT_HEIGHT = 500
ANNOTATION_FONT_SIZE = 10
