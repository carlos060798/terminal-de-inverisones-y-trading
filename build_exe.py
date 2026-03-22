"""
Build script — Empaqueta Quantum Retail Terminal como .exe
Ejecutar: py build_exe.py
Resultado: dist/QuantumTerminal.exe
"""
import PyInstaller.__main__
import os

BASE = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    os.path.join(BASE, "desktop_app.py"),
    "--name=QuantumTerminal",
    "--onefile",
    "--windowed",                          # Sin consola
    f"--icon={os.path.join(BASE, 'icon.ico')}",
    # Incluir todos los archivos del proyecto
    f"--add-data={os.path.join(BASE, 'app.py')};.",
    f"--add-data={os.path.join(BASE, 'ui_shared.py')};.",
    f"--add-data={os.path.join(BASE, 'database.py')};.",
    f"--add-data={os.path.join(BASE, 'ai_engine.py')};.",
    f"--add-data={os.path.join(BASE, 'valuation.py')};.",
    f"--add-data={os.path.join(BASE, 'pdf_parser.py')};.",
    f"--add-data={os.path.join(BASE, 'translator.py')};.",
    f"--add-data={os.path.join(BASE, 'excel_export.py')};.",
    f"--add-data={os.path.join(BASE, 'report_generator.py')};.",
    f"--add-data={os.path.join(BASE, 'icon.png')};.",
    f"--add-data={os.path.join(BASE, 'sections')};sections",
    f"--add-data={os.path.join(BASE, '.streamlit')};.streamlit",
    # Hidden imports que PyInstaller no detecta automáticamente
    "--hidden-import=streamlit",
    "--hidden-import=streamlit.web.bootstrap",
    "--hidden-import=streamlit.runtime.scriptrunner",
    "--hidden-import=yfinance",
    "--hidden-import=plotly",
    "--hidden-import=pdfplumber",
    "--hidden-import=openpyxl",
    "--hidden-import=fpdf2",
    "--hidden-import=webview",
    "--hidden-import=finvizfinance",
    "--hidden-import=fredapi",
    "--hidden-import=deep_translator",
    "--hidden-import=pandas_ta",
    "--hidden-import=pypfopt",
    "--hidden-import=streamlit_antd_components",
    "--noconfirm",
    "--clean",
])
