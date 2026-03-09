import sqlite3
from app.config import DB_NAME
import os

def get_connection():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transcription TEXT,
        location TEXT,
        hazard TEXT,
        severity TEXT,
        description TEXT,
        confidence REAL,
        latitude REAL,
        longitude REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP               
    )''')
    conn.commit()
    conn.close()