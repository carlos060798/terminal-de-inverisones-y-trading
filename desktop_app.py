"""
Investment Command Center — Desktop App
Ventana nativa de Windows usando pywebview + Streamlit en background.
Ejecutar: py desktop_app.py
"""
import subprocess
import threading
import time
import sys
import os
import socket
import webview

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT     = 8501
URL      = f"http://localhost:{PORT}"

# ── Icono inline base64 (chart emoji SVG convertido) ──────────────────────────
ICON_PATH = os.path.join(BASE_DIR, "icon.png")

_streamlit_proc = None


def _port_open(port: int) -> bool:
    """Devuelve True si el puerto ya está escuchando."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_streamlit():
    """Lanza Streamlit en background y espera hasta que levante."""
    global _streamlit_proc

    # Si ya hay algo en el puerto, no lanzamos de nuevo
    if _port_open(PORT):
        return

    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW  # Sin consola en Windows

    # Señal para que file_saver.py sepa que estamos en modo desktop
    os.environ["QUANTUM_DESKTOP"] = "1"

    _streamlit_proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            os.path.join(BASE_DIR, "app.py"),
            "--server.port",           str(PORT),
            "--server.headless",       "true",
            "--browser.gatherUsageStats", "false",
            "--server.enableCORS",     "false",
            "--server.enableXsrfProtection", "false",
        ],
        cwd=BASE_DIR,
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Esperar hasta 15 s a que el servidor responda
    for _ in range(30):
        if _port_open(PORT):
            return
        time.sleep(0.5)


def on_closed():
    """Al cerrar la ventana, matar Streamlit."""
    global _streamlit_proc
    if _streamlit_proc and _streamlit_proc.poll() is None:
        _streamlit_proc.terminate()
        try:
            _streamlit_proc.wait(timeout=5)
        except Exception:
            _streamlit_proc.kill()


def main():
    # 1. Lanzar Streamlit en hilo separado para no bloquear la UI
    t = threading.Thread(target=start_streamlit, daemon=True)
    t.start()
    t.join()  # Esperar a que el servidor esté listo

    # 2. Crear ventana nativa
    window = webview.create_window(
        title    = "📈 Investment Command Center",
        url      = URL,
        width    = 1440,
        height   = 900,
        min_size = (1024, 680),
        resizable= True,
        # Sin barra de dirección → parece app nativa
    )
    window.events.closed += on_closed

    # 3. Arrancar el bucle de eventos de la ventana
    #    gui='edgechromium' usa Microsoft Edge WebView2 (incluido en Windows 10/11)
    #    Si no está disponible, cae automáticamente a 'mshtml'
    try:
        webview.start(gui="edgechromium", debug=False)
    except Exception:
        webview.start(debug=False)


if __name__ == "__main__":
    main()
