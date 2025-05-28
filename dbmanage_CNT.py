# dbmanage_CNT_sqlalchemy.py (SQLAlchemy 버전)
from sqlalchemy import create_engine, Column, Integer, String, DateTime, PrimaryKeyConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from collections import defaultdict
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bills.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

class BillCount(Base):
    __tablename__ = 'bill_counts'
    age = Column(Integer, primary_key=True)
    propose_dt = Column(String, primary_key=True)
    count = Column(Integer, nullable=False)
    updated_at = Column(DateTime, nullable=False)


def init_CNTdb():
    Base.metadata.create_all(engine)


def save_bills_to_db(bills):
    """
    bills: list of (age, propose_dt) tuples
    """
    now = datetime.now()
    counter = defaultdict(int)
    for age, dt in bills:
        counter[(age, dt)] += 1

    session = SessionLocal()
    try:
        for (age, dt), count in counter.items():
            record = session.get(BillCount, (age, dt))
            if record:
                record.count = count
                record.updated_at = now
            else:
                record = BillCount(age=age, propose_dt=dt, count=count, updated_at=now)
                session.add(record)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[DB ERROR] {e}")
    finally:
        session.close()


def load_bills_from_db(age, year=None, max_age_minutes=300000000000):
    now = datetime.now()
    session = SessionLocal()
    result = []
    try:
        rows = session.query(BillCount).filter(BillCount.age == age).all()
        for row in rows:
            if (now - row.updated_at).total_seconds() > max_age_minutes * 60:
                return []
            try:
                dt = datetime.strptime(row.propose_dt.strip(), "%Y-%m-%d")
                if not year or dt.year == year:
                    result.extend([row.propose_dt] * row.count)
            except Exception as e:
                print(f"[파싱 실패] {row.propose_dt} → {e}")
    finally:
        session.close()
    return result


def clear_db(age=None):
    session = SessionLocal()
    try:
        if age is not None:
            session.query(BillCount).filter(BillCount.age == age).delete()
        else:
            session.query(BillCount).delete()
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[DB CLEAR ERROR] {e}")
    finally:
        session.close()
