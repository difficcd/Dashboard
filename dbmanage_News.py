from sqlalchemy import create_engine, Column, Integer, String, Text, UniqueConstraint, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import func
import urllib.parse
import re
import unicodedata
import os

# ✅ 절대경로로 DB 직접 지정
DATABASE_URL = "sqlite:///C:/Users/diffi/Desktop/Dashboard-main/Dashboard-main/bills.db"


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
    body = Column(Text, nullable=True) 

    __table_args__ = (
        UniqueConstraint("bill_id", "news_url", name="uix_bill_news"),
    )


# 법안 테이블 정의
class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)  # 변경: age → year
    title = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("year", "title", name="uix_year_title"),)
    propose_date = Column(Date, nullable=True)  



def update_news_body(bill_id: int, news_url: str, body_text: str):
    session = SessionLocal()
    try:
        news_url = news_url.strip()  # 정규화 제거
        news = session.query(BillNews).filter_by(bill_id=bill_id, news_url=news_url).first()
        if news:
            news.body = body_text
            session.commit()
            print(f"[뉴스 본문 저장 완료] {news.news_title} ({bill_id})")
        else:
            print(f"[뉴스 본문 저장 실패] 해당 뉴스 없음 → {bill_id} / {news_url}")
    except Exception as e:
        print(f"[뉴스 본문 저장 오류] {e}")
        session.rollback()
    finally:
        session.close()




# 결과 없을 때 여부 저장
def insert_no_news_placeholder(bill_title: str, year: int):
    session = SessionLocal()
    try:
        norm_title = normalize_title(bill_title)
        bill = session.query(Bill).filter_by(year=year, title=norm_title).first()
        if not bill:
            print(f"[PLACEHOLDER 오류] 해당 법안 없음 → {year} / {norm_title}")
            return

        # 이미 placeholder가 저장돼 있는지 확인
        exists = session.query(BillNews).filter_by(
            bill_id=bill.id,
            news_url="(없음)"
        ).first()
        if exists:
            print(f"[PLACEHOLDER 스킵] 이미 존재 → {year} / {norm_title}")
            return

        news = BillNews(
            bill_id=bill.id,
            news_title="(관련 뉴스 없음)",
            news_url="(없음)",
            comment_count=0,
            similarity="0.0"
        )
        session.add(news)
        session.commit()
        print(f"[PLACEHOLDER 저장] {year} / {norm_title}")
    except Exception as e:
        print(f"[PLACEHOLDER 저장 실패] {year} / {bill_title} → {e}")
    finally:
        session.close()




def get_news_by_bill_title(title: str, year: int):
    session = SessionLocal()
    try:
        norm_title = normalize_title(title)
        bill = session.query(Bill).filter_by(year=year, title=norm_title).first()
        if not bill:
            return []
        news_entries = session.query(BillNews).filter_by(bill_id=bill.id).all()
        return [(n.news_title, n.news_url) for n in news_entries]
    finally:
        session.close()



def is_exact_news_exist(bill_title: str, year: int, news_title: str, news_url: str) -> bool:
    session = SessionLocal()
    try:
        norm_title = normalize_title(bill_title)
        bill = session.query(Bill).filter_by(year=year, title=norm_title).first()
        if not bill:
            return False

        news_url = news_url.strip()
        parsed = urllib.parse.urlparse(news_url)
        cleaned_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        exists = session.query(BillNews).filter_by(
            bill_id=bill.id,
            news_title=news_title,
            news_url=cleaned_url
        ).first()
        return exists is not None
    finally:
        session.close()




def normalize_title(title):
    title = re.sub(r"\s+", " ", title)  # 여러 공백 → 하나로
    title = title.strip()
    title = unicodedata.normalize("NFC", title)  # 한글 정규화
    return title



def is_news_exist(bill_title: str, year: int) -> bool:
    session = SessionLocal()
    try:
        norm_title = normalize_title(bill_title)
        bill = session.query(Bill).filter_by(year=year, title=norm_title).first()
        if not bill:
            print(f"[DEBUG][is_news_exist] # 해당 법안이 DB에 없음: ({year}, '{norm_title}')")
            return False

        news_entries = session.query(BillNews).filter_by(bill_id=bill.id).all()
        if news_entries:
            print(f"[DEBUG][is_news_exist] ** 뉴스 존재함 → bill_id: {bill.id}, 개수: {len(news_entries)}")
            return True
        else:
            print(f"[DEBUG][is_news_exist] ** 뉴스 없음 → bill_id: {bill.id}")
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
    print(f"[DEBUG] __file__: {__file__ if '__file__' in globals() else 'N/A'}")


def insert_bill_news(bill_title, year, news_title, news_url, comment_count, similarity):
    session = SessionLocal()
    try:
        # 1. 관련 법안 ID 찾기
        norm_title = normalize_title(bill_title)
        bill = session.query(Bill).filter_by(title=norm_title, year=year).first()
        if not bill:
            print(f"[DB 오류] 해당 법안 없음 → {year} / {norm_title}")
            return

        # 2. URL 정리
        news_url = news_url.strip()
        parsed = urllib.parse.urlparse(news_url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # ✅ 3. 중복 확인
        exists = session.query(BillNews).filter_by(bill_id=bill.id, news_url=clean_url).first()
        if exists:
            print(f"[중복 스킵] 이미 저장된 뉴스입니다 → {bill_title} / {clean_url}")
            return

        # 4. 저장
        news = BillNews(
            bill_id=bill.id,
            news_title=news_title,
            news_url=clean_url,
            comment_count=comment_count,
            similarity=similarity,
        )
        session.add(news)
        session.commit()
    except Exception as e:
        print(f"[DB 오류] 뉴스 저장 실패 → {e}")
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


