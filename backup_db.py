"""
backup_db.py — Automatic database backup via Git commit
Copies the SQLite DB to a backup folder and commits it.

Usage:
  python backup_db.py              → Manual backup

For automatic scheduling, use Windows Task Scheduler (see below).
"""
import subprocess
import shutil
import os
from datetime import datetime

# ── Config ──
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(PROJECT_DIR, "investment_data.db")
BACKUP_DIR = os.path.join(PROJECT_DIR, "backups")


def run_git(*args):
    """Run a git command in the project directory."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def backup():
    """Create a timestamped backup of the DB and commit everything."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    date_label = now.strftime("%Y-%m-%d %H:%M")

    # 1. Create backup copy
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_file = os.path.join(BACKUP_DIR, f"investment_data_{timestamp}.db")

    if os.path.exists(DB_FILE):
        shutil.copy2(DB_FILE, backup_file)
        print(f"[OK] Backup creado: {backup_file}")
    else:
        print("[WARN] No se encontró la base de datos.")

    # Keep only last 10 backups to save space
    backups = sorted([
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("investment_data_") and f.endswith(".db")
    ])
    while len(backups) > 10:
        old = backups.pop(0)
        os.remove(os.path.join(BACKUP_DIR, old))
        print(f"[CLEAN] Eliminado backup antiguo: {old}")

    # 2. Git add all changes
    run_git("add", "-A")

    # 3. Check if there are changes to commit
    code, out, _ = run_git("status", "--porcelain")
    if not out.strip():
        print("[INFO] Sin cambios para commitear.")
        return

    # 4. Commit with timestamp
    msg = f"Backup automático - {date_label}\n\nBase de datos + cambios del proyecto"
    code, out, err = run_git("commit", "-m", msg)

    if code == 0:
        print(f"[OK] Commit creado: {msg.split(chr(10))[0]}")
    else:
        print(f"[ERROR] Error en commit: {err}")

    # 5. Show summary
    code, log, _ = run_git("log", "--oneline", "-5")
    print(f"\n--- Últimos 5 commits ---\n{log}")


if __name__ == "__main__":
    print("=" * 50)
    print("  Quantum Retail Terminal — Backup")
    print("=" * 50)
    backup()
    print("\n[DONE] Backup completado.")
