import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "beers.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS beers (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        total_drinks INTEGER DEFAULT 0,
        total_units REAL DEFAULT 0,
        alcohol_free INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS drink_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        units REAL,
        alcohol_free INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        user_id INTEGER PRIMARY KEY,
        weight REAL,
        sex TEXT
    )
    """)

    conn.commit()
    conn.close()



def reset_user_by_id(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        UPDATE beers
        SET total_drinks = 0,
            total_units = 0
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    