import ai_engine
import json

class ForensicAIAuditor:
    @staticmethod
    def generate_audit_commentary(ticker: str, health_data: dict, dna: dict):
        """
        Envía los datos forenses a Gemini para una interpretación narrativa profunda.
        """
        m_score = health_data.get("m_score", {})
        sloan = health_data.get("sloan", {})
        merton = health_data.get("merton", {})
        
        # Construir el prompt para el Auditor IA
        prompt = f"""
        Actúa como un Auditor Forense Senior y Analista de Riesgos. 
        Analiza los siguientes indicadores técnicos para la empresa {ticker}:

        1. Beneish M-Score: {m_score.get('score', 0):.2f} (Interpretación: {m_score.get('interpretation')})
        2. Sloan Ratio: {sloan.get('ratio', 0)*100:.2f}% (Status: {sloan.get('status')})
        3. Probabilidad de Default Merton: {merton.get('pd', 0)*100:.2f}% (Status: {merton.get('status')})
        
        Datos de Balance (SEC DNA):
        - Cash: {dna.get('cash', 0)}
        - Total Debt: {dna.get('total_debt', 0)}
        - Net Income: {dna.get('net_income', 0)}
        - Operating Cash Flow: {dna.get('operating_cash_flow', 0)}

        Escribe un informe de auditoría conciso (máx 150 palabras) destinado a un inversor institucional. 
        - Identifica la bandera roja más crítica (si existe).
        - Evalúa si la calidad de los beneficios es real o si hay manipulación (accruals).
        - Da una conclusión de 'Confianza Forense'.
        """
        
        try:
            return ai_engine.ask_gemini(prompt)
        except Exception as e:
            return (f"Error en la auditoría IA: {str(e)}", "none")


    @staticmethod
    def get_risk_labels(health_data):
        """Genera etiquetas de riesgo para el dashboard."""
        labels = []
        if health_data.get("m_score", {}).get("risk") == "High":
            labels.append("🚩 SOSPECHA DE MANIPULACIÓN")
        if abs(health_data.get("sloan", {}).get("ratio", 0)) > 0.15:
            labels.append("⚠️ BAJA CALIDAD DE BENEFICIOS")
        if health_data.get("merton", {}).get("pd", 0) > 0.05:
            labels.append("💀 RIESGO DE DEFAULT ELEVADO")
        return labels
