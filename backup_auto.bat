@echo off
REM Quantum Retail Terminal — Backup automático
REM Programa este .bat en el Programador de Tareas de Windows
REM para que se ejecute cada día/hora automáticamente.

cd /d "C:\Users\usuario\Videos\dasboard"
"C:\Users\usuario\AppData\Local\Programs\Python\Python313\python.exe" backup_db.py

REM Si quieres push automático a GitHub (después de configurar remote):
REM git push origin main
