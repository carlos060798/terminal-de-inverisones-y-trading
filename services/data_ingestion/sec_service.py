from sec_edgar_downloader import Downloader
import streamlit as st
import os

# Nota: El terminal ya tiene sec_api.py que usa la REST API de la SEC directamente.
# Este servicio se usa específicamente para DESCARGAR el archivo completo (HTML/TXT)
# para procesarlo con IA (RAG) o análisis de texto profundo.

def download_latest_filing(ticker, form_type="10-K", limit=1):
    """
    Descarga los últimos filings para un ticker dado.
    Utiliza sec-edgar-downloader que sistematiza la estructura de carpetas.
    """
    try:
        # La SEC requiere declarar quién es el User-Agent
        user_agent_parts = st.secrets.get("SEC_USER_AGENT", "QuantumTerminal admin@quantumterminal.ai").split(" ")
        company_name = user_agent_parts[0]
        email = user_agent_parts[1] if len(user_agent_parts) > 1 else "admin@quantumterminal.ai"
        
        # Inicializar el downloader localmente
        # Los archivos se guardan por defecto en la carpeta 'sec-edgar-filings'
        dl = Downloader(company_name, email)
        
        # Descargar el formulario solicitado
        print(f"[SEC SERVICE] Descargando {form_type} para {ticker}...")
        dl.get(form_type, ticker, limit=limit)
        
        # Los filings se guardan en ./sec-edgar-filings/TICKER/FORM_TYPE/...
        return True
        
    except Exception as e:
        print(f"[SEC SERVICE] Error en descarga de {ticker}: {e}")
        return False

def get_filing_path(ticker, form_type="10-K"):
    """Retorna la ruta local del último filing descargado (si existe)."""
    base_dir = "sec-edgar-filings"
    ticker_dir = os.path.join(base_dir, ticker.upper(), form_type)
    if os.path.exists(ticker_dir):
        # Buscar el archivo .txt o .html más reciente
        # (Esto es simplificado, en realidad sec-edgar-downloader crea carpetas con accession numbers)
        return ticker_dir
    return None

if __name__ == "__main__":
    download_latest_filing("AAPL", limit=1)
