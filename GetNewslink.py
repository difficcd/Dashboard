import json
import urllib.request
import urllib.parse
import time
import re
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer, util
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from insert_NewsScript import collect_and_store_missing_bodies
from dbmanage_News import (
    get_bills_by_year,
    insert_bill_by_year, 
    init_db, 
    insert_bill_news,
    get_news_by_bill_title,
    is_news_exist,
    is_exact_news_exist,
    insert_no_news_placeholder,
    update_missing_titles
    )


lock = Lock()
best_articles_by_title = {}



API_KEY = "68da180a494a4cc3b8add2071dc95242"
client_id = "CKb4pAJ84D6tVcCvpjka"
client_secret = "5PucVvnteo"
YEARS = list(range(2025, datetime.now().year + 1))  # 2016 ~ 올해
MAX_WORKERS = 8  # 병렬 스레드 개수 : 6~8 추천

# 임베딩 모델 (스레드 안전)
model = SentenceTransformer("all-MiniLM-L6-v2")
embedding_cache = {}

def get_embedding(text: str):
    if text not in embedding_cache:
        embedding_cache[text] = model.encode(text, convert_to_tensor=True)
    return embedding_cache[text]

# Selenium 기본 옵션 – 스레드마다 새 인스턴스를 씀
base_options = Options()
base_options.add_argument("--headless=new")
base_options.add_argument("--no-sandbox")
base_options.add_argument("--disable-dev-shm-usage")

API_URL = "https://open.assembly.go.kr/portal/openapi/TVBPMBILL11"


def clean_url(url: str) -> str:
    url = url.strip()
    # 불필요한 query 제거 (예: sid=100)
    parsed = urllib.parse.urlparse(url)
    cleaned = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return cleaned


def _get_bill_rows_by_age(age: int, p_size: int = 1000):
    """특정 *대수*의 모든 법안 row를 반환."""
    rows, p_index = [], 1
    while True:
        params = {
            "KEY": API_KEY,
            "Type": "json",
            "AGE": age,
            "pIndex": p_index,
            "pSize": p_size,
        }
        url = f"{API_URL}?{urllib.parse.urlencode(params)}"
        try:
            time.sleep(0.1)  # 너무 빠른 호출 방지
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            items = data.get("TVBPMBILL11", [])
            page_rows = items[1].get("row", []) if len(items) > 1 else []
            if not page_rows:
                break
            rows.extend(page_rows)
            if len(page_rows) < p_size:
                break
            p_index += 1
        except Exception as e:
            print(f"[API 오류] {age}대 {p_index}페이지 → {e}")
            break
    return rows


def get_bill_titles_by_year(year: int):
    """주어진 *year*(YYYY) 에 발의된 모든 법안명을 리스트로 반환."""
    titles = []
    # 20‧21‧22대 국회 범주에 모두 질의한 뒤 날짜로 필터링
    for age in (20, 21, 22):
        for row in _get_bill_rows_by_age(age):
            propose_dt = row.get("PROPOSE_DT", "")  # YYYYMMDD 형태
            if propose_dt.startswith(str(year)):
                title = row.get("BILL_NAME", "").strip()
                if title:
                    titles.append(title)
    # 중복 제거 (원본 순서 유지)
    return list(dict.fromkeys(titles))



def get_comment_count(news_url: str, driver: webdriver.Chrome) -> int:
    """네이버 뉴스 URL에서 댓글 수를 반환."""
    try:
        driver.get(news_url)
        time.sleep(1)
        # "더보기" 버튼 자동 클릭
        while True:
            try:
                more_btn = driver.find_element(By.CLASS_NAME, "u_cbox_btn_more")
                driver.execute_script("arguments[0].click();", more_btn)
                time.sleep(0.4)
            except Exception:
                break
        return len(driver.find_elements(By.CSS_SELECTOR, "span.u_cbox_contents"))
    except Exception as e:
        print(f"   [댓글 실패] {news_url} → {e}")
        return 0


def search_news_unique(title: str, sim_threshold: float = 0.0): 
    # 네이버 뉴스 검색기능이 관련성을 어느정도 보장하므로 0.0 으로 유사도기준 완화
    # 반대 의미의 기사일 경우에만 걸러내도록 함 (거의 X)

    cleaned = re.sub(r"일부개정법률안.*|전부개정법률안.*|일부개정.*|전부개정.*", "", title)
    cleaned = re.sub(r"\(.*?\)", "", cleaned).strip()
    query = urllib.parse.quote(cleaned)
    url = f"https://openapi.naver.com/v1/search/news?query={query}&display=100&start=1&sort=date"
    req = urllib.request.Request(url)
    for k, v in (
        ("X-Naver-Client-Id", client_id),
        ("X-Naver-Client-Secret", client_secret),
        ("User-Agent", "Mozilla/5.0"),
    ):
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("items", [])
        cut_off = datetime.now() - timedelta(days=800)
        title_emb = get_embedding(title)

        best_article = None
        driver = webdriver.Chrome(options=base_options)

        for item in items:
            raw_title = item["title"].replace("<b>", "").replace("</b>", "")
            link = item["link"]
            pubDate = item["pubDate"]
            try:
                pub_dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z").replace(tzinfo=None)
                if pub_dt < cut_off:
                    continue
            except Exception:
                continue
            if "n.news.naver.com" not in link:
                continue

            sim = util.cos_sim(title_emb, get_embedding(raw_title)).item()
            if sim < sim_threshold:
                continue

            c_cnt = get_comment_count(link, driver)
            if c_cnt < 5:
                continue

            if (
                best_article is None or
                c_cnt > best_article[2] or
                (c_cnt == best_article[2] and sim > best_article[3])
            ):
                best_article = (raw_title, link, c_cnt, sim)

        driver.quit()
        return best_article
    except Exception as e:
        print(f"[뉴스 검색 오류] {title}: {e}")
        return None



# 스레드 작업 함수
def process_title(index: int, title: str, year: int):
    """뉴스 DB에 저장되지 않은 법안에 대해 뉴스 검색 및 저장"""
    result = search_news_unique(title)
    if result:
        best_title, best_link, c_cnt, sim = result
        best_articles_by_title[title] = result

        # 🔽 먼저 URL 정제
        cleaned_url = clean_url(best_link)

        # ✅ 중복 여부 먼저 체크
        if is_exact_news_exist(title, year, best_title, cleaned_url):
            print(f"\n[{index+1:03}] ⏩ 이미 저장된 뉴스 → 스킵")
            return

        # ✅ 탐색 결과 출력
        print(f"\n[{index+1:03}] ✅ {best_title} ({c_cnt}개, 유사도 {sim:.3f})")
        print(f"[{index+1:03}] {title} → 🔎 최다 댓글 뉴스기사 링크 : {best_link}")

        # ✅ 뉴스 저장
        insert_bill_news(
            bill_title=title,
            year=year,
            news_title=best_title,
            news_url=cleaned_url,  # 정제된 URL로 저장
            comment_count=c_cnt,
            similarity=sim,
        )


    else:
        print(f"\n[{index+1:03}] ❌ 관련 뉴스 없음: {title}")
        insert_no_news_placeholder(title, year)  # ← 이 줄 추가





if __name__ == "__main__":
    init_db()

    update_missing_titles()
    # bill_news 에 bills 의 title 칼럼에서 법안명 가져옴 (db 데이터 무결성 확인용)

    for year in YEARS:
        print(f"\n==================== {year}년 법안 ====================")
        titles = get_bills_by_year(year)
        if titles:
            print(f"[INFO] DB에서 {year}년 법안 {len(titles)}개를 가져왔습니다. \n")
        else:
            print(f"[INFO] DB에 {year}년 자료가 없어 API를 호출합니다. \n")
            titles = get_bill_titles_by_year(year)
            print(f"[INFO] {year}년 법안 {len(titles)}개 수집 완료. \n")
            saved = skipped = 0
            for t in titles:
                try:
                    insert_bill_by_year(year, t)
                    saved += 1
                except Exception as e:
                    print(f"[DB 저장 실패] {t} → {e}")
                    skipped += 1
            print(f"[DB 저장 결과] 시도: {len(titles)}, 성공: {saved}, 스킵: {skipped}")

        title_to_index = {}

        # 아직 처리되지 않은 법안만 필터링
        titles_without_news = []
        for idx, title in enumerate(titles):
            title_to_index[title] = idx
            exists = is_news_exist(title, year)
            print(f"뉴스 존재 여부: {title} ({year}) → {exists}")
            if not exists:
                titles_without_news.append(title)

        # DB에서 이미 뉴스가 저장된 법안에 대한 출력
        printed_idx = 1  # 1부터 시작하는 출력용 인덱스

        for title in set(titles) - set(titles_without_news):
            news_list = get_news_by_bill_title(title, year)
            for news_title, news_url in news_list:
                print(f"\n[{printed_idx:03}] 🗂️  {news_title} (이미 저장됨)")
                print(f"[{printed_idx:03}] {title} → 🔎 뉴스기사 링크 : {news_url}")
                printed_idx += 1

        # 🔄 저장되지 않은 뉴스는 병렬 처리
        if titles_without_news:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [
                    executor.submit(process_title, title_to_index[t], t, year)
                    for t in titles_without_news
                ]
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"[스레드 예외 발생] {e}")
                        import traceback
                        traceback.print_exc()

        # 결과 요약 출력
        for title in titles:
            article = best_articles_by_title.get(title)
            if article:
                best_title, url, c_cnt, sim = article
                if c_cnt >= 5:
                    print(f"\n   ✅ {best_title} ({c_cnt}개, 유사도 {sim:.3f})")
                    print(f"{title} → 🔎 최다 댓글 뉴스기사 링크 : {url}")


        time.sleep(2)


    collect_and_store_missing_bodies() # 일단 1000개로 예상
    print("\n본문 db 저장 완료")



        

