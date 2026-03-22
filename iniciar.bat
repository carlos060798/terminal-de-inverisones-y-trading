@echo off
title Quantum Retail Terminal
echo.
echo  ========================================
echo   Quantum Retail Terminal v6.0
echo   Iniciando servidor...
echo  ========================================
echo.

cd /d "%~dp0"

:: Buscar Python
where python >nul 2>&1 && set PY=python || set PY="C:\Users\usuario\AppData\Local\Programs\Python\Python313\python.exe"

:: Abrir navegador en 3 segundos
start "" "http://localhost:8501"

:: Iniciar Streamlit
%PY% -m streamlit run app.py --server.port=8501 --server.headless=true --browser.gatherUsageStats=false

pause
