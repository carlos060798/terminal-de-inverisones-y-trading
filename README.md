# 📈 Investment Command Center

Dashboard privado de inversiones — 100% local, sin suscripciones.

## Instalación rápida

### 1. Requisitos
- Python 3.9 o superior → https://www.python.org/downloads/

### 2. Instalar dependencias
Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
pip install -r requirements.txt
```

### 3. Lanzar la app
```bash
streamlit run app.py
```

Se abrirá automáticamente en tu navegador en: **http://localhost:8501**

---

## Secciones

| Sección | Qué hace |
|---|---|
| 📄 Analizador de Acciones | Sube PDFs financieros y extrae métricas automáticamente. Compara contra umbrales ideales y genera un radar de puntuación. |
| 👁️ Watchlist & Cartera | Agrega tickers, obtiene precios en tiempo real vía yfinance, muestra gráficos de distribución y candlestick con MA20/MA50. |
| 📓 Diario de Trading | Registra operaciones, calcula P&L automáticamente, curva de equity, win rate y factor de beneficio. |

## Métricas Ideales (Manual Definitivo de Inversión)

| Métrica | Umbral |
|---|---|
| Crecimiento de Ingresos | ≥ 10% |
| Margen de Beneficio Neto | ≥ 15% |
| ROE | ≥ 15% |
| Ratio Corriente | ≥ 1.5x |
| P/E Ratio | ≤ 25x |
| Deuda / Patrimonio | ≤ 1.0x |

## Datos
Los datos se guardan en `investment_data.db` (SQLite) — no se pierden al cerrar la app.
