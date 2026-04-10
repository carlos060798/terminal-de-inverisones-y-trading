from apscheduler.schedulers.background import BackgroundScheduler
import streamlit as st
import database as db
# import services.data_ingestion.reddit_service as reddit (Sin Reddit/Twitter por política institucional)
import services.data_ingestion.tiingo_service as tiingo
import services.data_ingestion.finnhub_service as finnhub
import services.data_ingestion.macro_service as macro
import services.data_ingestion.crypto_service as crypto

def run_sync_all():
    """
    Función orquestadora que sincroniza todas las fuentes activas.
    Utiliza las librerías instaladas y guarda los resultados en SQLite.
    """
    print("[DATA-SYNC] Iniciando ciclo completo de sincronización...")
    
    # Lista de tickers para seguimiento (Watchlist + Benchmarks)
    try:
        wl = db.get_watchlist()
        tickers = wl['ticker'].tolist() if not wl.empty else ["SPY", "QQQ", "AAPL", "MSFT", "TSLA"]
    except Exception:
        tickers = ["SPY", "QQQ", "AAPL", "MSFT", "TSLA"]
    
    # 1. Sentimiento Reddit (DESACTIVADO por arquitectura institucional)
    # reddit.sync_reddit_sentiment(tickers)
    
    # 2. Noticias Tiingo y Ratings Finnhub (Procesar los top 10 para balancear carga)
    for ticker in tickers[:10]:
        tiingo.sync_tiingo_news(ticker)
        finnhub.sync_finnhub_analysts(ticker)
        
    # 3. Datos Globales Cripto (Market Cap, Dominancia BTC)
    crypto.sync_coingecko_global()
    
    print("[DATA-SYNC] Ciclo de sincronización completado exitosamente.")

def init_scheduler():
    """
    Inicializa el BackgroundScheduler de Python.
    En el contexto de Streamlit, esta función debe ser llamada con @st.cache_resource
    para evitar que cada recarga del navegador lance un nuevo hilo de ejecución.
    """
    scheduler = BackgroundScheduler()
    
    # Programación de tareas
    
    # Tarea 1: Ciclo completo cada 4 horas (Ratings, Noticias)
    scheduler.add_job(run_sync_all, 'interval', hours=4, id="full_sync_job")
    
    # Tarea 2: Sincronización rápida de Cripto (cada 15 minutos)
    scheduler.add_job(crypto.sync_coingecko_global, 'interval', minutes=15, id="crypto_sync_job")
    
    # Tarea 3: Datos Macro (PIB/Inflación) - Una vez al mes por ser datos de baja frecuencia
    # Se programa para el día 1 de cada mes a la media noche.
    scheduler.add_job(macro.sync_worldbank_macro, 'cron', day=1, hour=0, id="macro_sync_job")
    
    try:
        scheduler.start()
        print("[DATA-SYNC] APScheduler iniciado en segundo plano (Background Thread).")
    except (KeyboardInterrupt, SystemExit):
        pass
        
    return scheduler
