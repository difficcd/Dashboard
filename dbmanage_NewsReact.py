
# news sentiment 에 news_url column 추가해야함


# 경로수정 필요함 dashboard dashboard 로 이동시켜야함 
# 현재 C:\Users\diffi\Desktop\Dashboard-main\bills.db" 에 있음 (통합이안됨)

# id title && 그래프에 대한 정보 매칭
# bill_id 는 통용되는 key 값이라 db 끼리 접근할때 꼭 필요
# title 은 가시성을 위해서 넣는 것 권장 

# dbmanage_NewsReact.py
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from datetime import datetime

Base = declarative_base()
engine = create_engine("sqlite:///C:/Users/diffi/Desktop/Dashboard-main/Dashboard-main/bills.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class NewsSentiment(Base):
    __tablename__ = "news_sentiment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(Integer, nullable=False)
    title = Column(String)
    news_url = Column(String, nullable=False)
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("bill_id", "news_url"),)


# ✅ 외부에서 호출할 수 있는 초기화 함수
def init_sentiment_table():
    Base.metadata.create_all(bind=engine)
    print("DB 초기화 완료하였습니다.\n")


# ✅ 분석 여부 확인
def is_sentiment_already_analyzed(bill_id: int, news_url: str) -> bool:
    session = SessionLocal()
    try:
        return session.query(NewsSentiment).filter_by(bill_id=bill_id, news_url=news_url).first() is not None
    finally:
        session.close()



def insert_sentiment_result(bill_id: int, title: str, news_url: str, sentiment_counts: dict):
    session = SessionLocal()
    try:
        new_entry = NewsSentiment(
            bill_id=bill_id,
            title=title,
            news_url=news_url,  
            positive_count=sentiment_counts.get("긍정적 인식", 0),
            negative_count=sentiment_counts.get("부정적 인식", 0),
            neutral_count=sentiment_counts.get("중립", 0),
        )
        session.add(new_entry)
        session.commit()
        print(f"✅ 저장 완료: {bill_id} / {title}")
    except Exception as e:
        print(f"❌ 저장 실패: {bill_id} → {e}")
        session.rollback()
    finally:
        session.close()


