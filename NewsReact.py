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

def has_enough_comments(news_url, min_comments=0):
    try:
        driver.get(news_url)
        time.sleep(1)  #댓글 크롤링 : 네트워크 시간 고려
        while True:
            try:
                more_btn = driver.find_element(By.CLASS_NAME, "u_cbox_btn_more")
                driver.execute_script("arguments[0].click();", more_btn)
                time.sleep(0.5)
            except:
                break

        comments = driver.find_elements(By.CSS_SELECTOR, "span.u_cbox_contents")
        return len(comments) >= min_comments

    except Exception as e:
        print(f"   [댓글 수집 실패] {news_url} → {e}")
        return False




def search_news_unique(title, sim_threshold=0.7):
    query = urllib.parse.quote(title)
    url = f"https://openapi.naver.com/v1/search/news?query={query}&display=30&start=1&sort=date" 

    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    request.add_header("User-Agent", "Mozilla/5.0")

    try:
        response = urllib.request.urlopen(request)
        data = json.loads(response.read().decode("utf-8"))
        items = data.get("items", [])

        six_months_ago = datetime.now() - timedelta(days=180)
        valid_items = []
        has_news = False
        has_high_comment_news = False

        for item in items:
            raw_title = item["title"].replace("<b>", "").replace("</b>", "")
            link = item["link"]
            pubDate = item["pubDate"]

            try:
                pub_date = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z").replace(tzinfo=None)
                if pub_date < six_months_ago:
                    continue
            except:
                continue

            if "n.news.naver.com" not in link:
                continue

            pattern = r'\b' + re.escape(title) + r'\b'
            if not re.search(pattern, raw_title, re.IGNORECASE):
                continue

            cur_embed = get_embedding(raw_title)
            is_similar = False
            for prev_title in printed_titles:
                prev_embed = get_embedding(prev_title)
                similarity = util.pytorch_cos_sim(cur_embed, prev_embed).item()
                if similarity > sim_threshold:
                    is_similar = True
                    break

            if not is_similar:
                valid_items.append((raw_title, link))
                printed_titles.append(raw_title)

        if valid_items:
            print(f"\n📌 {title}")  # 법안명 출력
            has_news = True

            for raw_title, link in valid_items:
                if has_enough_comments(link, min_comments=5):
                    print(f"   ✅ {raw_title} → {link}")
                    has_high_comment_news = True
                else:
                    print(f"   - {raw_title} → {link}")

        return has_high_comment_news

    except Exception as e:
        print(f"[뉴스 검색 오류] {title}: {e}")
    return False



# --- 실행 ---
if __name__ == "__main__":
    age = 22
    init_db()

    # 1️⃣ DB 확인
    titles = get_bills_by_age(age)
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
