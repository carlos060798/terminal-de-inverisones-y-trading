# Conectar con GitHub (gratis, opcional)

## 1. Crear cuenta en GitHub
- Ve a https://github.com y crea una cuenta gratuita

## 2. Crear repositorio
- Click en "New repository"
- Nombre: `quantum-retail-terminal`
- Selecciona **Private** (privado, solo tú lo ves)
- NO marques "Add README" (ya tienes uno)
- Click "Create repository"

## 3. Conectar desde tu PC
Abre Git Bash o terminal y ejecuta:

```bash
cd "C:\Users\usuario\Videos\dasboard"
git remote add origin https://github.com/TU_USUARIO/quantum-retail-terminal.git
git branch -M main
git push -u origin main
```

Te pedirá usuario y contraseña de GitHub.
(Si usas 2FA, necesitas un Personal Access Token en vez de contraseña)

## 4. Backup automático a GitHub
Descomenta la última línea de `backup_auto.bat`:
```bat
git push origin main
```

Así cada noche a las 23:00 se hará commit + push automático.

## 5. Push manual
```bash
cd "C:\Users\usuario\Videos\dasboard"
git push
```
