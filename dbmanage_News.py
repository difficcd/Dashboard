from sqlalchemy import create_engine, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
import re
import unicodedata
import os

# ✅ 절대경로로 DB 직접 지정
DATABASE_URL = "sqlite:///C:/Users/diffi/Desktop/NewsReact/bills.db"

# SQLAlchemy 기본 설정
Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

# 법안 테이블 정의
class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    age = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("age", "title", name="uix_age_title"),)


def normalize_title(title):
    title = re.sub(r"\s+", " ", title)  # 여러 공백 → 하나로
    title = title.strip()
    title = unicodedata.normalize("NFC", title)  # 한글 정규화
    return title


def get_bills_by_age(age):
    session = SessionLocal()
    try:
        bills = session.query(Bill).filter_by(age=age).all()
        print(f"[DEBUG] {age}대 국회 DB 조회 결과: {len(bills)}개")
        if bills:
            print(f"[DEBUG] 첫 3개 예시: {[bill.title for bill in bills[:3]]}")
        return [bill.title for bill in bills]
    finally:
        session.close()


def init_db():
    db_path = DATABASE_URL.replace("sqlite:///", "")
    print(f"[DEBUG] DB 경로: {db_path}")
    if not os.path.exists(db_path):
        print("[INFO] DB가 존재하지 않아 새로 생성합니다.")
        Base.metadata.create_all(bind=engine)
    else:
        print("[INFO] 기존 DB 사용 중 - 삭제되지 않았는지 확인하세요.")
    print(f"[DEBUG] os.getcwd(): {os.getcwd()}")
    print(f"[DEBUG] __file__: {__file__}")


def insert_bill(age, title):
    session = SessionLocal()
    try:
        norm_title = normalize_title(title)
        exists = session.query(Bill).filter_by(age=age, title=norm_title).first()
        if not exists:
            new_bill = Bill(age=age, title=norm_title)
            session.add(new_bill)
            session.commit()
            print(f"[DEBUG] 저장 성공: {norm_title}")
            return True
        else:
            print(f"[DEBUG] 중복으로 스킵됨: {norm_title}")
        return False
    except Exception as e:
        print(f"[DB 오류] '{title}' 저장 실패: {e}")
        session.rollback()
        return False
    finally:
        session.close()
