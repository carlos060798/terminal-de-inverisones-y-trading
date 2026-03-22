"""
💎 Quantum Retail Terminal — Desktop Launcher
Doble clic para abrir. No muestra consola (.pyw)
Abre como app nativa con pywebview (o navegador si no está instalado).
"""
import subprocess
import threading
import time
import sys
import os
import socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8501
URL = f"http://localhost:{PORT}"

_proc = None

def _port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def start_streamlit():
    global _proc
    if _port_open(PORT):
        return
    flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    os.environ["QUANTUM_DESKTOP"] = "1"
    _proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run",
         os.path.join(BASE_DIR, "app.py"),
         "--server.port", str(PORT),
         "--server.headless", "true",
         "--browser.gatherUsageStats", "false",
         "--server.enableCORS", "false",
         "--server.enableXsrfProtection", "false"],
        cwd=BASE_DIR, creationflags=flags,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if _port_open(PORT):
            return
        time.sleep(0.5)

def kill_streamlit():
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except Exception:
            _proc.kill()

def main():
    try:
        import webview

        # Lanzar Streamlit en hilo
        t = threading.Thread(target=start_streamlit, daemon=True)
        t.start()
        t.join()

        # Ventana nativa (sin barra de URL = parece app de escritorio)
        icon_path = os.path.join(BASE_DIR, "icon.png")
        window = webview.create_window(
            title="💎 Quantum Retail Terminal",
            url=URL,
            width=1440,
            height=900,
            min_size=(1024, 680),
            resizable=True,
        )
        window.events.closed += kill_streamlit

        try:
            webview.start(gui="edgechromium", debug=False)
        except Exception:
            webview.start(debug=False)

    except ImportError:
        # Sin pywebview → abrir en navegador normal
        start_streamlit()
        import webbrowser
        webbrowser.open(URL)
        # Mantener vivo hasta que cierren
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            kill_streamlit()

if __name__ == "__main__":
    main()
