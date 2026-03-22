@echo off
:: Crea un acceso directo en el escritorio
set SHORTCUT="%USERPROFILE%\Desktop\Quantum Terminal.lnk"
set TARGET="%~dp0iniciar.bat"
set ICON="%~dp0assets\icon.ico"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\Quantum Terminal.lnk'); $s.TargetPath = '%~dp0iniciar.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Quantum Retail Terminal'; $s.Save()"

echo.
echo  Acceso directo creado en el Escritorio!
echo  Busca "Quantum Terminal" en tu escritorio.
echo.
pause
