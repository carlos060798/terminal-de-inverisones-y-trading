# Changelog

## [7.0.0] - Data Fabric Engine
### Added
- **Data Fabric Architecture**: Implementado patrón de diseño "Data Fabric" asíncrono con `ThreadPoolExecutor`, optimizado explícitamente para sortear las bloqueos de interfaz del render loop de Streamlit (`adapters/execution_engine.py`).
- **Provider Adapters (49 totales)**: 
  - **Macro**: FRED, World Bank, IMF, ECB, OECD, BIS, US Treasury, BLS, CEPAL.
  - **Stocks**: YFinance, Alpha Vantage, Polygon, Marketstack, SEC EDGAR, Quandl, Stooq, IEX Cloud, Intrinio, Simfin, Finviz.
  - **Crypto**: Binance, CoinGecko, CoinMarketCap, Kraken, CryptoCompare, Messari.
  - **Forex**: ECB Forex, Open Exchange Rates, Fixer, CurrencyFreaks, OANDA.
  - **Commodities**: EIA, USDA, World Bank Commodities, CME.
  - **News & Sentiment**: NewsAPI, GDELT, Reddit, StockTwits, Reuters RSS, Seeking Alpha RSS, Twitter/X.
  - **Volatility**: CBOE VIX, CFTC COT, Deribit, Nasdaq Options, Calc VIX.
  - **Alternative**: Google Trends, Wikipedia PV, OpenBB, Fear & Greed.
- **Mixins Modulares**: `RestMixin` (manejo de sesiones+rutas auth), `LibraryMixin` (carga lazy wrapper), `CsvMixin` (descarga y parsing in-memory).
- **Resource Orchestrator**: `adapters/resource_budget.py` integrado para monitorizar consumo de CPU/RAM (límite de seguridad 70% CPU / 1.5GB RAM) e ingesta con Rate Limiting de algoritmos *Token Bucket*.
- **Circuit Breaker Inteligente**: `adapters/circuit_breaker.py` con estados automáticos (CLOSED, OPEN, HALF_OPEN) mapeados por `provider_id`. Umbral de 3 fallos y reseteos programables previenen asfixiar el render bajo caídas HTTP.
- **Data Health Dashboard**: Nueva pestaña dedicada interactiva (`sections/data_health.py`) habilitada en `app.py` que despliega listado central consolidado y visualización Mockup para los 49 proveedores.

### Changed
- Refactorización de `data_sources.py`: La API pública para el resto del código y secciones previas mantiene compatibilidad retroactiva completa (_backward-compatible wrappers_), pero su lógica engarza al 100% con `ExecutionEngine` permitiendo paralelizmo.
- Bump central de Sistema v5.0 -> v7.0 en `sections/system_health.py` incluyendo anclajes al nuevo panel Health.
- Requisitos de base actualizados (`requirements.txt`) mapeando compatibilidad masiva para los frameworks conectores propuestos.

### Fixed
- Resueltos cuellos de botella del Dashboard bajo demoras en API. Los TTL (Time To Live) por providor garantizan respuestas inmediatas (~5ms) tras cold starts.
