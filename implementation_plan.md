# Programa General de Implementación: Quantum Terminal v6.0

Este documento establece la hoja de ruta estratégica para rediseñar y potenciar el Quantum Retail Terminal hacia su versión 6.0. La ejecución se divide en 6 Sprints ágiles enfocados en entregar valor continuo, priorizando las bases de diseño y rendimiento estructural antes de añadir la nueva lógica de análisis y AI.

---

## 📅 Cronograma General (Roadmap por Sprints)

### 🏎️ Sprint 1: Fundamentos Visuales y Estructura Base
**Objetivo:** Establecer el sistema de diseño atómico y una navegación tipo "Terminal Profesional".
- **CSS & UI Core:** Migración del CSS monolítico a tokens de diseño en `assets/theme.css`. Creación de la librería `utils/visual_components.py` (componentes reutilizables como *pills*, *badges* y tarjetas base).
- **Tooling de Rendimiento:** Implementar fetching paralelo (`ThreadPoolExecutor`) y añadir los índices faltantes en la base de datos `SQLite`.
- **Navegación:** Reestructuración de `app.py` hacia una navegación lateral iconográfica y simplificada usando `sac.menu`.
- **Status Bar:** Implementación de una barra inferior/superior persistente con métricas macro en vivo.

### 📊 Sprint 2: Dashboard & Portfolio Analytics
**Objetivo:** Transformar la vista principal en un centro de mando interactivo y denso en información.
- **Layout Multipanel:** Refactorización de `sections/dashboard.py` hacia una estructura de grillas modular.
- **Position Cards:** Miniaturización de la tabla de posiciones activas incluyendo *sparklines* de precio incorporados directamente en las tarjetas.
- **Analítica de Portafolio:** Introducción de Heatmaps de PnL en el calendario y Atribución Factorial para las posiciones activas.
- **Stress Testing Engine:** Primera iteración del simulador de impacto en la cartera basado en escenarios macroeconómicos predefinidos.

### 📈 Sprint 3: Stock Analyzer Institucional
**Objetivo:** Aumentar la profundidad técnica y fundamental del escrutinio de activos individuales.
- **Cadena de Opciones (Options Viewer):** Integración inicial en el layout actual del Analyzer.
- **Patrones Técnicos:** Implementación de un detector automático de formaciones (Pattern Scanner / TA-Lib integration).
- **Earnings Analysis:** Gráfica de impacto histórico y análisis de correlación post-sorpresa de EPS.
- **Convergence Score:** Primer modelo de unificación de análisis Fundamental + Técnico + Sentimiento en una sola métrica de convicción.

### ⚙️ Sprint 4: Backtesting & Quant Engine
**Objetivo:** Multiplicar por 100 el rendimiento de la evaluación de estrategias mediante vectorización.
- **Migración a Vectorbt:** Reescribir el motor del archivo `sections/backtest.py` para aprovechar computación vectorial masiva.
- **Evaluación a Nivel Portafolio:** Expandir la capacidad para hacer backtesting de carteras enteras en lugar de acciones aisladas.
- **Nuevas Métricas de Riesgo:** Integración de Ulcer Index, Factor de Recuperación y Ratios de Cola.
- **Cimientos de ML:** Proof-of-concept visual para construcción de estrategias asistidas por Machine Learning.

### 🧩 Sprint 5: Nuevos Módulos y Macro Global
**Objetivo:** Expandir la funcionalidad para emular terminales como Bloomberg incorporando el panorama general.
- **Options Desk Completo:** Nuevo módulo dedicado (`sections/options_desk.py`) incluyendo superficie de Volatilidad Implícita (IV) 3D.
- **Global Market Heatmap:** Mapa de calor mundial cruzando acciones, sectores y forex.
- **News Intelligence:** Módulo segregado de `news_intel.py` enfocado en "Sentimiento" general.
- **Modelos Macro:** Integración visual de un modelo de "Rotación Sectorial" y reportes CFTC/COT para Forex.

### 🧠 Sprint 6: AI-First & Performance Mastery
**Objetivo:** Refinar la capa de inteligencia artificial para operarla en tiempo real, junto a las mejoras de experiencia (UX/UI).
- **Streaming AI:** Modificación de `ai_router.py` y llamadas a backend (OpenAI, Gemini, etc.) para entregar respuestas en tiempo real por tokens, eliminando la espera.
- **Contexto Predictivo:** Enriquecer los prompts mediante inyección en el nivel inferior de variables del momento (VIX, % intradiario del ticker).
- **Consenso Multi-Modelo:** Creación de pipelines que llamen de forma paralela a 3 LLMs para buscar "consenso de opinión".
- **Búsqueda (Ctrl+K):** Implementar la búsqueda rápida mediante componentes customizados o expansores nativos.

---

## 🏗️ Requerimientos Inmediatos para Ejecución (Sprint 1)

Para proteger la estabilidad del flujo de trabajo actual e iniciar el **Sprint 1**, este es el plan de abordaje nivel archivo:

1. **`assets/theme.css`:** Crear de cero basándose en la especificación entregada y vincularlo en la configuración general de Streamlit.
2. **`utils/visual_components.py`:** Generar un módulo de ayuda con funciones limpias para renderizar KPIs y componentes HTML parametrizados. Reemplazar iterativamente los `st.markdown` aislados en la interfaz por estas funciones.
3. **`app.py`:** Mudar el enrutamiento para aprovechar un sidebar estético avanzado y estructurar el bloque de "Top Ribbon" (o Status bar).

## 💬 User Review Required

> [!CAUTION]
> He consolidado todo el plan en sus respectivos Sprints. Como los cambios en el **Sprint 1** (modificar CSS y rediseñar el enrutamiento en `app.py`) impactarán visualmente en todos los módulos de inmediato:
> 
> **¿Cuentas con mi aprobación para entrar a ciegas en la fase de código y ejecutar el Sprint 1 ahora mismo?** Iniciaré creando los tokens de diseño, la librería de componentes base, y aplicando el nuevo layout lateral a la plataforma existente.
