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

# 뉴스링크 저장 테이블 저장
class BillNews(Base):
    __tablename__ = "bill_news"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(Integer, nullable=False)  # bills.id를 외래키로 연결해도 좋음
    news_title = Column(String, nullable=False)
    news_url = Column(String, nullable=False)
    comment_count = Column(Integer, default=0)
    similarity = Column(String, default="0.0")  # float으로 해도 무방

    __table_args__ = (
        UniqueConstraint("bill_id", "news_url", name="uix_bill_news"),
    )


# 법안 테이블 정의
class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)  # ✅ 변경: age → year
    title = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("year", "title", name="uix_year_title"),)



def normalize_title(title):
    title = re.sub(r"\s+", " ", title)  # 여러 공백 → 하나로
    title = title.strip()
    title = unicodedata.normalize("NFC", title)  # 한글 정규화
    return title



def is_news_exist(bill_title: str, year: int) -> bool:
    print(f"[DEBUG][is_news_exist] 호출됨 - year: {year}, title: '{bill_title}'")
    session = SessionLocal()
    try:
        norm_title = normalize_title(bill_title)
        print(f"[DEBUG][is_news_exist] 정규화된 title: '{norm_title}'")

        bill = session.query(Bill).filter_by(year=year, title=norm_title).first()
        if not bill:
            print(f"[DEBUG][is_news_exist] 해당 법안이 DB에 없음: ({year}, '{norm_title}')")
            return False

        news = session.query(BillNews).filter_by(bill_id=bill.id).first()
        if news:
            print(f"[DEBUG][is_news_exist] 뉴스 존재함 → bill_id: {bill.id}, news_url: {news.news_url}")
            return True
        else:
            print(f"[DEBUG][is_news_exist] 뉴스 없음 → bill_id: {bill.id}")
            return False
    finally:
        session.close()




def get_bills_by_year(year):
    session = SessionLocal()
    try:
        bills = session.query(Bill).filter_by(year=year).all()
        print(f"[DEBUG] {year}년 DB 조회 결과: {len(bills)}개")
        if bills:
            print(f"[DEBUG] 첫 3개 예시: {[bill.title for bill in bills[:3]]}")
        return [bill.title for bill in bills]
    finally:
        session.close()



def init_db():
    db_path = DATABASE_URL.replace("sqlite:///", "")
    print(f"[DEBUG] DB 경로: {db_path}")
    
    if not os.path.exists(db_path):
        print("[INFO] DB 파일 없음 → 새로 생성합니다.")
    else:
        print("[INFO] DB 파일 있음 → 테이블은 생성되지 않았을 수 있음. create_all 실행.")

    # ✅ 이 부분이 핵심: 존재하는 테이블은 무시하고, 없는 테이블은 생성됨
    Base.metadata.create_all(bind=engine)

    print(f"[DEBUG] os.getcwd(): {os.getcwd()}")
    print(f"[DEBUG] __file__: {__file__}")



def insert_bill_news(bill_title, year, news_title, news_url, comment_count, similarity):
    session = SessionLocal()
    try:
        norm_title = normalize_title(bill_title)
        bill = session.query(Bill).filter_by(year=year, title=norm_title).first()
        if not bill:
            print(f"[WARN] 법안 미존재 → {year}년: {bill_title}")
            return False
        exists = session.query(BillNews).filter_by(bill_id=bill.id, news_url=news_url).first()
        if exists:
            print(f"[DEBUG] 이미 저장됨 → {bill_title} - {news_url}")
            return False
        new_entry = BillNews(
            bill_id=bill.id,
            news_title=news_title,
            news_url=news_url,
            comment_count=comment_count,
            similarity=str(similarity)
        )
        session.add(new_entry)
        session.commit()
        print(f"[INFO] 뉴스 저장 완료 → {news_title}")
        return True
    except Exception as e:
        print(f"[DB 오류] 뉴스 저장 실패 → {e}")
        session.rollback()
        return False
    finally:
        session.close()



def insert_bill_by_year(year, title):
    session = SessionLocal()
    try:
        norm_title = normalize_title(title)
        exists = session.query(Bill).filter_by(year=year, title=norm_title).first()
        if not exists:
            new_bill = Bill(year=year, title=norm_title)
            session.add(new_bill)
            session.commit()
            print(f"[DEBUG] 저장 성공: {year}년 → {norm_title}")
            return True
        else:
            print(f"[DEBUG] 중복으로 스킵됨: {year}년 → {norm_title}")
        return False
    except Exception as e:
        print(f"[DB 오류] '{title}' 저장 실패: {e}")
        session.rollback()
        return False
    finally:
        session.close()

