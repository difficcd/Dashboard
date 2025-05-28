# dbmanage_sqlalchemy.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from collections import defaultdict
from datetime import datetime
import os

# DB 설정
DB_PATH = "committee.db"
DB_URL = f"sqlite:///{DB_PATH}"

Base = declarative_base()
engine = create_engine(DB_URL, echo=False)
Session = sessionmaker(bind=engine)


# ORM 모델 정의
class CommitteeStat(Base):
    __tablename__ = "committee_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    age = Column(Integer, nullable=False)
    committee = Column(String, nullable=False)
    count = Column(Integer, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("age", "committee", name="uix_age_committee"),
    )


# 테이블 초기화
def init_db():
    Base.metadata.create_all(engine)


# 저장
def save_to_db(committee_counts, age):
    now = datetime.now().isoformat()
    with Session() as session:
        for committee, count in committee_counts.items():
            existing = session.query(CommitteeStat).filter_by(age=age, committee=committee).first()
            if existing:
                existing.count = count
                existing.updated_at = now
            else:
                new_row = CommitteeStat(age=age, committee=committee, count=count, updated_at=now)
                session.add(new_row)
        session.commit()


# 조회
def load_from_db(ages, max_age_minutes=30):
    now = datetime.now()
    result = defaultdict(int)
    total = 0

    with Session() as session:
        for age in ages:
            rows = session.query(CommitteeStat).filter_by(age=age).all()
            if not rows:
                return {}, 0
            for row in rows:
                updated_time = datetime.fromisoformat(row.updated_at)
                if (now - updated_time).total_seconds() > max_age_minutes * 60:
                    return {}, 0
                result[row.committee] += row.count
                total += row.count
    return dict(result), total


# 삭제
def clear_db(age=None):
    with Session() as session:
        if age is not None:
            session.query(CommitteeStat).filter_by(age=age).delete()
        else:
            session.query(CommitteeStat).delete()
        session.commit()
