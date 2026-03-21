"""
launcher.pyw — Lanzador silencioso del Investment Command Center
Doble clic para abrir el dashboard sin ninguna ventana de terminal.
"""
import subprocess
import webbrowser
import time
import sys
import os

# Directorio donde vive app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Arrancar Streamlit en segundo plano (sin ventana de consola en Windows)
CREATE_NO_WINDOW = 0x08000000
proc = subprocess.Popen(
    [sys.executable, "-m", "streamlit", "run",
     os.path.join(BASE_DIR, "app.py"),
     "--server.headless", "true",
     "--server.port", "8501",
     "--browser.gatherUsageStats", "false"],
    cwd=BASE_DIR,
    creationflags=CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Esperar a que levante y abrir el navegador
time.sleep(3)
webbrowser.open("http://localhost:8501")
