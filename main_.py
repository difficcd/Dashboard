from fastapi import FastAPI, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import RedirectResponse
from dash_news_app import create_dash_app, create_dash_app_from_result # 후자는 데이터 받아서 결과 산출
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import create_engine
from dbmanage_News import SessionLocal, BillNews
from dbmanage_NewsReact import NewsSentiment, NewsComment
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from insert_NewsScript import collect_body_for_url
from GetNewslink import search_news_unique
from GetNewsReact import load_comments, analyze_sentiment
from types import SimpleNamespace
from insert_NewsScript import get_article_body

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






@app.post("/analyze_news")
def analyze_news(request: Request, title: str = Form(...), db: Session = Depends(get_db)):
    title = title.strip()


    if not title or not title.endswith(("법률안", "법안", "법")):
        return templates.TemplateResponse("index_news.html", {
            "request": request,
            "error": "법안명을 정확히 입력하세요. 예: '청소년보호법'",
            "title": "",
            "article_title": "법안명을 정확히 입력하세요.",
            "article_url": "",
            "article_html": "법안명을 정확히 입력하세요. 예: '청소년보호법'",
            "total_comments": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "total": 0,
            "comments": [],
            "query": title,
            "dash_url": "",
            "has_prev": False,
            "has_next": False,
            "current_page": 1,
            "total_pages": 1,
            "start_page": 1,
            "end_page": 1,
            "size": 1,
            "result": "",
        })
    
    sentiment_row = (
        db.query(NewsSentiment)
        .filter(NewsSentiment.title == title)
        .order_by(NewsSentiment.id)
        .first()
    )

    if sentiment_row:
    # ✔ 존재할 경우 해당 id 기준으로 페이지 번호 계산
        sentiment_id = sentiment_row.id

        # 전체 몇 개 있는지 알아야 페이지 번호 계산 가능
        all_ids = db.query(NewsSentiment.id).order_by(NewsSentiment.id).all()
        all_ids_list = [r[0] for r in all_ids]

        try:
            index = all_ids_list.index(sentiment_id)
            per_page = 1
            page = (index // per_page) + 1
            # 🔁 페이지로 리다이렉트
            return RedirectResponse(url=f"/index_news?page={page}", status_code=302)
        except ValueError:
            pass  # 못 찾으면 그냥 분석 진행


    # 1. 기사 찾기
    result = search_news_unique(title)
    if not result:
        return templates.TemplateResponse("index_news.html", {
            "request": request,
            "error": f"'{title}' 관련 뉴스 기사를 찾을 수 없습니다.",
            "title": "",
            "article_title": f"'{title}' 관련 뉴스 기사를 찾을 수 없습니다.",
            "article_url": "",
            "article_html": " 관련 뉴스 기사를 찾을 수 없습니다.",
            "total_comments": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "total": 0,
            "comments": [],
            "query": title,
            "dash_url": "",
            "has_prev": False,
            "has_next": False,
            "current_page": 1,
            "total_pages": 1,
            "start_page": 1,
            "end_page": 1,
            "size": 1,
            "result": "",
        })

    news_title, news_url, comment_count, sim = result
    comment_url = news_url.replace("/article/", "/article/comment/")

    # 2. 댓글 수집
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    try:
        comments = load_comments(driver, comment_url)
    finally:
        driver.quit()
    
    # 3. 감정 분석
    sentiment_result = analyze_sentiment(comments)
    print(f"분석 결과 디버깅 : {sentiment_result}\n")

    # 원래 comments 딕셔너리 리스트 → 템플릿이 원하는 필드명으로 변환
    comment_objs = [
        SimpleNamespace(
            author=c.get("작성자", ""), 
            text=c.get("댓글", ""),  
            sentiment=c.get("감정", ""),
            date=c.get("작성일자", ""),
            like=c.get("공감수", 0),
            dislike=c.get("비공감수", 0)
        )
        for c in comments
    ]

    print(comment_objs[0].text)  # 또는 .author
    news_html = get_article_body(news_url.strip())

    
    dash_app_live = create_dash_app_from_result(sentiment_result)

    app.mount("/dash_news_app_live", WSGIMiddleware(dash_app_live.server))

    dash_url_live = f"/dash_news_app_live/"

    return templates.TemplateResponse("index_news.html", {
        "request": request,
        "error": "",
        "title": title,
        "article_title": news_title,
        "article_url": news_url,
        "article_html": news_html,
        "total_comments": len(comment_objs),
        "positive_count": sentiment_result["긍정적 인식"],
        "negative_count": sentiment_result["부정적 인식"],
        "neutral_count": sentiment_result["중립"],
        "total": sum(sentiment_result.values()),
        "comments": comment_objs,  # 여기만 핵심
        "query": title,
        "dash_url_live": dash_url_live,
        "dash_url": "",
        "has_prev": False,
        "has_next": False,
        "current_page": 1,
        "total_pages": 1,
        "start_page": 1,
        "end_page": 1,
        "size": 1,
        "result": "",
    })



    

# db  기반 기본 페이지
@app.get("/index_news")
def get_index_news(request: Request, page: int = 1, db: Session = Depends(get_db)):
    per_page = 1
    total_bills = db.query(NewsSentiment).count()
    total_pages = math.ceil(total_bills / per_page)

    if page < 1 or page > total_pages:
        page = 1

    offset = (page - 1) * per_page

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
            "title": "",
            "article_title": "데이터가 없습니다.",
            "article_url": "",
            "article_html": "데이터베이스에 일치하는 검색 결과가 없습니다. 검색 기능을 이용하세요.",
            "total_comments": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "total": 0,
            "comments": [],
            "query": "",
            "dash_url": "",
            "has_prev": False,
            "has_next": False,
            "current_page": 1,
            "total_pages": 1,
            "start_page": 1,
            "end_page": 1,
            "size": 1,
            "result": "",
        })

    dash_app = create_dash_app()
    app.mount("/dash_news_app", WSGIMiddleware(dash_app.server))

    bill_news = (
        db.query(BillNews)
        .filter(
            BillNews.bill_id == news_sentiment.bill_id,
            BillNews.news_url == news_sentiment.news_url
        )
        .first()
    )

    comments = (
        db.query(NewsComment)
        .filter(
            NewsComment.bill_id == news_sentiment.bill_id,
            NewsComment.news_url == news_sentiment.news_url
        )
        .order_by(NewsComment.id.asc())
        .all()
    )

    # iframe용 Dash URL 생성
    dash_url = f"/dash_news_app/?page={page}"

    PAGE_DISPLAY_COUNT = 5
    start_page = max(1, page - PAGE_DISPLAY_COUNT // 2)
    end_page = min(total_pages, start_page + PAGE_DISPLAY_COUNT - 1)
    if (end_page - start_page) < (PAGE_DISPLAY_COUNT - 1):
        start_page = max(1, end_page - PAGE_DISPLAY_COUNT + 1)

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
        "total": news_sentiment.positive_count + news_sentiment.negative_count + news_sentiment.neutral_count,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "current_page": page,
        "total_pages": total_pages,
        "start_page": start_page,
        "end_page": end_page,
        "size": per_page,
        "query": "",
        "committee": "",
        "result": "",
        "comments": comments,
        "dash_url_live": "",
        "dash_url": dash_url  
    })

