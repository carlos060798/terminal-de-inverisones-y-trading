import pandas as pd
from database import get_connection
import datetime
from pathlib import Path

def load_md(path_str):
    path = Path(path_str)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"Error: Archivo no encontrado en {path_str}"

def save_entry_to_db(entry_data):
    """
    Saves a trading plan/journal entry to the trading_plan_entries table.
    entry_data: dict with keys matching table columns
    """
    conn = get_connection()
    c = conn.cursor()
    
    columns = ", ".join(entry_data.keys())
    placeholders = ", ".join(["?" for _ in entry_data])
    values = tuple(entry_data.values())
    
    query = f"INSERT INTO trading_plan_entries ({columns}) VALUES ({placeholders})"
    
    try:
        c.execute(query, values)
        conn.commit()
    finally:
        conn.close()

def get_recent_entries(limit=10):
    conn = get_connection()
    try:
        df = pd.read_sql_query(f"SELECT * FROM trading_plan_entries ORDER BY created_at DESC LIMIT {limit}", conn)
        return df
    finally:
        conn.close()
