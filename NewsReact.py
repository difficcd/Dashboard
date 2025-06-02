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
from dbmanage_News import SessionLocal, Bill, get_bills_by_age, insert_bill, init_db

# --- 설정 ---
API_KEY = "68da180a494a4cc3b8add2071dc95242"
client_id = "CKb4pAJ84D6tVcCvpjka"
client_secret = "5PucVvnteo"

# 임베딩 모델
model = SentenceTransformer('all-MiniLM-L6-v2')
printed_titles = []
embedding_cache = {}

# 셀레니움 설정
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)

# --- 함수 ---

def get_embedding(text):
    if text not in embedding_cache:
        embedding_cache[text] = model.encode(text, convert_to_tensor=True)
    return embedding_cache[text]

def get_bill_titles_by_age(age):
    url = "https://open.assembly.go.kr/portal/openapi/TVBPMBILL11"
    bill_titles = []
    p_index = 1
    p_size = 1000

    while True:
        params = {
            "KEY": API_KEY,
            "Type": "json",
            "pIndex": p_index,
            "pSize": p_size,
            "AGE": age
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"

        try:
            time.sleep(0.1)
            req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read())

            items = data.get("TVBPMBILL11", [])
            rows = items[1].get("row", []) if len(items) > 1 else []

            if not rows:
                break

            for row in rows:
                bill_name = row.get("BILL_NAME", "").strip()
                if bill_name:
                    bill_titles.append(bill_name)

            if len(rows) < p_size:
                break

            p_index += 1

        except Exception as e:
            print(f"[ERROR] {age}대 {p_index}페이지 에러: {e}")
            break

    return bill_titles

def get_comment_count(news_url):
    try:
        driver.get(news_url)
        time.sleep(1)

        # 더보기 버튼 계속 클릭
        while True:
            try:
                more_btn = driver.find_element(By.CLASS_NAME, "u_cbox_btn_more")
                driver.execute_script("arguments[0].click();", more_btn)
                time.sleep(0.5)
            except:
                break

        comments = driver.find_elements(By.CSS_SELECTOR, "span.u_cbox_contents")
        count = len(comments)

        return count

    except Exception as e:
        print(f"   [댓글 수집 실패] {news_url} → {e}")
        return 0



def search_news_unique(title, sim_threshold=0.6):  # 유사도 임계값 설정
    cleaned_title = re.sub(r'일부개정법률안.*|전부개정법률안.*|일부개정.*|전부개정.*', '', title)
    cleaned_title = re.sub(r'\(.*?\)', '', cleaned_title).strip()
    query = urllib.parse.quote(cleaned_title)
    url = f"https://openapi.naver.com/v1/search/news?query={query}&display=100&start=1&sort=date"

    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    request.add_header("User-Agent", "Mozilla/5.0")

    try:
        response = urllib.request.urlopen(request)
        data = json.loads(response.read().decode("utf-8"))
        items = data.get("items", [])

        one_year_ago = datetime.now() - timedelta(days=800)
        article_candidates = []

        print(f"\n📌 {title} (→ 검색어: {cleaned_title})")

        title_emb = get_embedding(title)

        for item in items:
            raw_title = item["title"].replace("<b>", "").replace("</b>", "")
            link = item["link"]
            pubDate = item["pubDate"]

            try:
                pub_date = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z").replace(tzinfo=None)
                if pub_date < one_year_ago:
                    continue
            except:
                continue

            if "n.news.naver.com" not in link:
                continue

            sim = util.cos_sim(title_emb, get_embedding(raw_title)).item()
            if sim < sim_threshold:
                continue

            comment_count = get_comment_count(link)
            article_candidates.append((raw_title, link, comment_count, sim))
            printed_titles.append(raw_title)

        if article_candidates:
            best_article = sorted(article_candidates, key=lambda x: x[2], reverse=True)[0]
            max_comment = best_article[2]
            if max_comment >= 5:
                print(f"   ✅ {best_article[0]} ({max_comment}개, 유사도: {best_article[3]:.2f}) → {best_article[1]}")
                return True
            else:
                print(f"   ⚠️ 뉴스 {len(article_candidates)}개, 최대 댓글수 {max_comment}개, 유사도 최댓값 {best_article[3]:.2f} → 조건 미충족")
        else:
            print("   ❌ 조건 충족 뉴스 없음")

    except Exception as e:
        print(f"[뉴스 검색 오류] {title}: {e}")

    return False




# --- 실행 ---
if __name__ == "__main__":
    age = 22
    init_db()

    # 1️⃣ DB 확인
    titles = get_bills_by_age(age)
    titles = list(dict.fromkeys(titles)) #완전한 중복 제거 (최신 순서 유지)


    if titles:
        print(f"[INFO] DB에서 {age}대 국회 법안 {len(titles)}개를 가져왔습니다.\n")
    else:
        print(f"[INFO] DB에 {age}대 국회 법안이 없어, API에서 가져옵니다.\n")
        titles = get_bill_titles_by_age(age)

        print(f"[INFO] {age}대 국회에서 {len(titles)}개의 법안명을 수집했습니다.\n")

        # 2️⃣ DB에 저장 (중복 확인 포함)
        saved, skipped = 0, 0
        for title in titles:
            try:
                insert_bill(age, title)
                saved += 1
            except Exception as e:
                print(f"[DB 저장 실패] {title} → {e}")
                skipped += 1

        print(f"[DB 저장 결과] 총 시도: {len(titles)}, 성공: {saved}, 스킵: {skipped}\n")

    # 3️⃣ 뉴스 검색 및 출력
    for i, title in enumerate(titles, 1):
        result = search_news_unique(title)
        if result:
            print(f"👉 {i}. {title} → ✅ 댓글 많은 뉴스 있음\n")
            
        time.sleep(0.1)

    driver.quit()
