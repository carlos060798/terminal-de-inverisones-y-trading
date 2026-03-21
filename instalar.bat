@echo off
echo ============================================
echo  Investment Command Center - Instalacion
echo ============================================
echo.
echo Instalando dependencias Python...
py -m pip install -r requirements.txt
py -m pip install pywebview
echo.
echo ============================================
echo  Instalacion completada!
echo  Ahora puedes abrir "Abrir Dashboard.bat"
echo ============================================
pause
