"""services/backup_service.py - Automated Local Backups for SQLite DB."""
import os
import shutil
import time
from datetime import datetime

def run_backup(db_path: str, backup_dir: str = "backups"):
    """
    Creates a timestamped copy of the database file.
    """
    if not os.path.exists(db_path):
        print(f"[BACKUP] Source DB not found at {db_path}")
        return False
        
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = os.path.basename(db_path)
    backup_filename = f"backup_{timestamp}_{db_name}"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"[BACKUP] Success: {backup_path}")
        
        # Cleanup old backups (keep last 5)
        _cleanup_old_backups(backup_dir, limit=5)
        return backup_path
    except Exception as e:
        print(f"[BACKUP] Error: {e}")
        return False

def _cleanup_old_backups(backup_dir: str, limit: int = 5):
    """Keep only the most recent 'limit' backups."""
    try:
        backups = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("backup_")]
        backups.sort(key=os.path.getmtime, reverse=True)
        
        if len(backups) > limit:
            for old_backup in backups[limit:]:
                os.remove(old_backup)
                print(f"[BACKUP] Removed old backup: {old_backup}")
    except Exception as e:
        print(f"[BACKUP] Cleanup error: {e}")

if __name__ == "__main__":
    # Test
    run_backup("investment_data.db")
