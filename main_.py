from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from dbmanage_News import SessionLocal, BillNews, Bill
from dbmanage_NewsReact import NewsSentiment
import math
import os

DATABASE_URL = "sqlite:///C:/Users/diffi/Desktop/Dashboard-main/Dashboard-main/bills.db"

# SQLAlchemy 기본 설정
#Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
app = FastAPI()
templates = Jinja2Templates(directory="dash_news/html")

# DB 연결 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 정적 파일 경로 mount (예: /static)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "dash_news/html")), name="static")



@app.get("/index_news")
def get_index_news(request: Request, page: int = 1, db: Session = Depends(get_db)):
    per_page = 1

    # 전체 법안 수
    total_bills = db.query(NewsSentiment).count()
    total_pages = math.ceil(total_bills / per_page)

    if page < 1 or page > total_pages:
        page = 1  # 잘못된 페이지 처리

    offset = (page - 1) * per_page

    # 뉴스 감성 분석 데이터에서 1개 선택
    news_sentiment = (
        db.query(NewsSentiment)
        .order_by(NewsSentiment.id)
        .offset(offset)
        .limit(per_page)
        .first()
    )

    if not news_sentiment:
        return templates.TemplateResponse("index_news.html", {
            "request": request,
            "error": "데이터를 찾을 수 없습니다.",
        })

    # 해당 법안의 뉴스 본문 가져오기
    bill_news = (
        db.query(BillNews)
        .filter(
            BillNews.bill_id == news_sentiment.bill_id,
            BillNews.news_url == news_sentiment.news_url
        )
        .first()
    )

    return templates.TemplateResponse("index_news.html", {
        "request": request,
        "title": news_sentiment.title,
        "article_title": bill_news.news_title if bill_news else "",
        "article_url": bill_news.news_url if bill_news else "",
        "article_html": bill_news.body if bill_news else "",
        "total_comments": bill_news.comment_count if bill_news else 0,
        "positive_count": news_sentiment.positive_count,
        "negative_count": news_sentiment.negative_count,
        "neutral_count": news_sentiment.neutral_count,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "current_page": page,
        "total_pages": total_pages
    })
