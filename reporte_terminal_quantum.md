# Informe de Capacidades: Quantum Retail Terminal — Pro Edition

## 1. Introducción
**Quantum Retail Terminal** es una plataforma institucional de inversiones diseñada para el sector retail. Combina análisis fundamental avanzado, datos alternativos en tiempo real, inteligencia artificial (RAG & Agentes) y herramientas de gestión de cartera en una interfaz unificada de alto rendimiento.

## 2. Funcionalidades de la Aplicación

### 📊 Dashboard & KPIs
- **Seguimiento de Cartera**: Visualización de P&L acumulado, Rentabilidad Diaria y Curva de Equidad.
- **Métricas de Riesgo**: Cálculo en tiempo real de Sharpe Ratio, Sortino Ratio, Drawdown Máximo y VaR (Value at Risk).
- **Asignación de Activos**: Gráficos interactivos de distribución por sector, industria y tipo de activo.

### 🔍 Análisis de Acciones (Stock Analyzer)
- **Valoración Fundamental**: Módulos de DCF (Discounted Cash Flow), Benjamin Graham Intrinsic Value y modelos de múltiplos (PE/PS/PB).
- **Health Scores**: Puntuaciones propietarias de salud financiera basadas en Altman-Z Score, Piotroski-F Score y Beneish M-Score.
- **Parser de Informes**: Extracción automática de datos desde archivos PDF (10-K, 10-Q) mediante `pdfplumber` y `PyMuPDF`.
- **Integración de TradingView**: Gráficos técnicos avanzados con indicadores integrados.

### 📈 Screener & Quant (Buscador de Oportunidades)
- **Filtros Personalizados**: Búsqueda por métricas de valoración, crecimiento, dividendos y volatilidad.
- **Heatmaps del Sector**: Mapas de calor interactivos para identificar rotación de capital en sectores de EE.UU.
- **Quant Score**: Algoritmo que clasifica acciones basado en Momentum, Calidad y Valor.

### 🧠 Inteligencia Artificial (AI Engine)
- **Agentes Autónomos**: Implementación de `LangGraph` para realizar tesis de inversión complejas analizando múltiples fuentes de datos.
- **Análisis de Gráficos (Vision)**: Capacidad para "leer" gráficos de precios mediante modelos vision (Gemini/GPT-4o) para detectar patrones técnicos.
- **RAG (Retrieval-Augmented Generation)**: Chat inteligente entrenado con documentos PDF locales usando `ChromaDB` para responder preguntas sobre tesis específicas.
- **Sentimiento**: Análisis de titulares de noticias y tweets mediante `FinBERT` (HuggingFace).

### 🌍 Macro Context (Entorno Global)
- **Integración FRED**: Acceso a indicadores de la Reserva Federal (Inflación, Desempleo, PIB).
- **Curva de Tipos**: Visualización interactiva de la Yield Curve de bonos del tesoro.
- **Forex & Crypto**: Seguimiento de pares de divisas, materias primas (Oro, Petróleo) y criptoactivos (vía CoinGecko).

### 🧪 Backtesting & Simulaciones
- **Backtest Vectorizado**: Pruebas rápidas de estrategias técnicas (Cruces de Medias, RSI, Bandas de Bollinger).
- **Monte Carlo**: Simulaciones de 1,000+ escenarios para predecir la probabilidad de éxito de un portafolio.
- **Optimización Markowitz**: Cálculo de la "Frontera Eficiente" para maximizar retorno por unidad de riesgo.

### 📝 Diario de Trading & Planificación
- **Journaling**: Registro de operaciones con etiquetas de psicología (FOMO, Greed, Fear).
- **Plan de Inversión**: Herramientas de dimensionamiento de posición (Kelly Criterion) y gestión de stop-loss.

## 3. Servicios Consumibles (APIs y Orígenes de Datos)

| Tipo de Servicio | Proveedores Integrados | Propósito |
| :--- | :--- | :--- |
| **Financiero Core** | `yfinance`, `Finviz`, `SEC EDGAR` | Precios, fundamentales y estados financieros. |
| **Macroeconomía** | `FRED API`, `IMF`, `BLS` | Indicadores globales y política monetaria. |
| **Modelos de IA** | `Gemini`, `Groq`, `OpenRouter` | Análisis generativo y razonamiento financiero. |
| **Cripto / Forex** | `CoinGecko`, `Binance`, `Oanda` | Datos en tiempo real de activos alternativos. |
| **Fuentes de Texto** | `Reddit`, `Twitter`, `GDELT` | Monitoreo de sentimiento y tendencias sociales. |

## 4. Herramientas y Stack Tecnológico

### Lenguajes y Frameworks
- **Python 3.x**: Lenguaje núcleo.
- **Streamlit**: Framework de interfaz de usuario.
- **SQLite**: Motor de base de datos local persistente.

### Análisis y Datos
- **Procesamiento**: `Pandas`, `NumPy`, `SciPy`.
- **Análisis Quant**: `QuantStats`, `PyPortfolioOpt`, `VectorBT`.
- **ML & AI**: `Scikit-learn`, `HuggingFace`, `LangGraph`, `ChromaDB`.

### Visualización y Reportes
- **Gráficos**: `Plotly`, `E-Charts`, `Lightweight Charts`.
- **UI Components**: `Ant Design` (via `streamlit-antd-components`), `AgGrid`.
- **Exportación**: `OpenPyXL` (Excel) y `FPDF2` (Generación de Reportes PDF).

---
*Este informe ha sido generado automáticamente para el usuario Antigravity el 04 de Abril de 2026.*
