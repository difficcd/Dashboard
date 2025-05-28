# dbmanage_CNT.py (변경된 구조: 날짜별 건수 저장)
import sqlite3
from datetime import datetime
from collections import defaultdict
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bills.db")


def init_CNTdb():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bill_counts (
                age INTEGER,
                propose_dt TEXT,
                count INTEGER,
                updated_at TEXT,
                PRIMARY KEY (age, propose_dt)
            )
        """)
        conn.commit()


def save_bills_to_db(bills):
    """
    bills: list of (age, propose_dt) tuples
    """
    now = datetime.now().isoformat()
    counter = defaultdict(int)
    for age, dt in bills:
        counter[(age, dt)] += 1

    rows = [(age, dt, count, now) for (age, dt), count in counter.items()]

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.executemany("""
            INSERT OR REPLACE INTO bill_counts (age, propose_dt, count, updated_at)
            VALUES (?, ?, ?, ?)
        """, rows)
        conn.commit()


def load_bills_from_db(age, year=None, max_age_minutes=60):
    if not os.path.exists(DB_PATH):
        return []

    now = datetime.now()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT propose_dt, count, updated_at FROM bill_counts WHERE age = ?
        """, (age,))
        rows = cur.fetchall()

    result = []
    for dt_str, count, updated_at in rows:
        try:
            if updated_at:
                updated_time = datetime.fromisoformat(updated_at)
                if (now - updated_time).total_seconds() > max_age_minutes * 60:
                    return []  # 오래된 데이터면 수집하도록 유도

            dt = datetime.strptime(dt_str.strip(), "%Y-%m-%d")
            if not year or dt.year == year:
                result.extend([dt_str] * count)  # count만큼 복원
        except Exception as e:
            print(f"[파싱 실패] {dt_str} → {e}")
    return result


def clear_db(age=None):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        if age is not None:
            cur.execute("DELETE FROM bill_counts WHERE age = ?", (age,))
        else:
            cur.execute("DELETE FROM bill_counts")
        conn.commit()
