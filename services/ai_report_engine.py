import streamlit as st
import json
from services.text_service import generate

def generate_ai_report(ticker: str, full_data: dict) -> str:
    """
    Generates a structured markdown report using the active LLM.
    `full_data` contains SEC, YF, and PDF data aggregated in the analyzer.
    """
    st.toast(f"Generando reporte IA para {ticker}...", icon="🤖")
    
    # Serializar financials_annual del PDF parser según Sprint 4
    pdf_data = full_data.get("pdf", {})
    financials = pdf_data.get("financials_annual", {})
    
    context = f"TICKER: {ticker}\n"
    context += f"FINANCIALS ANNUAL: {json.dumps(financials, indent=2)}\n"
    context += f"PRO TIPS: {json.dumps(pdf_data.get('pro_tips', []))}\n"
    context += f"SWOT: {json.dumps(pdf_data.get('swot', {}))}\n"
    context += f"ANALYSIS VERDICT: {json.dumps(full_data.get('verdict', {}))}\n"
    
    system = "Eres un analista Senior de Wall Street. Genera un reporte Markdown en español con:\n## 🏛️ Resumen Ejecutivo\n## 📈 Análisis de Ingresos y Márgenes\n## 💰 Free Cash Flow & Calidad de Ganancias\n## ⚠️ Riesgos Detectados\n## 🎯 Valoración y Precio Objetivo\n## ✅ Veredicto Final"
    prompt = f"Analiza la siguiente data financiera extraída de InvestingPro y reportes SEC:\n{context}\n\nEscribe el reporte completo y profesional usando la estructura solicitada."
    
    try:
        report, _ = generate(prompt, system, max_tokens=2000, chain_type="analysis")
        if report:
            return report
    except Exception as e:
        return f"Error generando reporte: {e}"
        
    return "Error al contactar el LLM. Posible problema de servicio."
