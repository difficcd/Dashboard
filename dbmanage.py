# dbmanage.py
import sqlite3
from collections import defaultdict
from datetime import datetime

DB_PATH = "committee.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS committee_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            age INTEGER,
            committee TEXT,
            count INTEGER,
            updated_at TEXT,
            UNIQUE(age, committee) ON CONFLICT REPLACE
        )
    """)
    conn.commit()
    conn.close()

def save_to_db(committee_counts, age):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now().isoformat()
    for committee, count in committee_counts.items():
        cur.execute("""
            INSERT OR REPLACE INTO committee_stats (age, committee, count, updated_at)
            VALUES (?, ?, ?, ?)
        """, (age, committee, count, now))
    conn.commit()
    conn.close()

def load_from_db(ages, max_age_minutes=30):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total = 0
    
    now = datetime.now()
    result = defaultdict(int)
    for age in ages:
        cur.execute("SELECT committee, count, updated_at FROM committee_stats WHERE age = ?", (age,))
        rows = cur.fetchall()
        if not rows:
            return {}, 0
        for committee, count, updated_at in rows:
            updated_time = datetime.fromisoformat(updated_at)
            if (now - updated_time).total_seconds() > max_age_minutes * 60:
                return {}, 0
            result[committee] += count
            total += count
    return dict(result), total

def clear_db(age=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if age is not None:
        cur.execute("DELETE FROM committee_stats WHERE age = ?", (age,))
    else:
        cur.execute("DELETE FROM committee_stats")
    conn.commit()
    conn.close()

