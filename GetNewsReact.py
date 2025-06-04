from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from transformers import pipeline
import matplotlib.pyplot as plt
import matplotlib
import time
from dbmanage_News import SessionLocal, BillNews

session = SessionLocal()

SIZE = 10
raw_results = (
    session.query(BillNews.news_url)
    .filter(BillNews.news_url != "(없음)")
    .order_by(BillNews.comment_count.desc())
    .all()
)

# 중복 제거 (앞에서부터 순서 유지)
seen = set()
urls = []
for row in raw_results:
    url = row.news_url.strip()
    if url not in seen:
        seen.add(url)
        urls.append(url)
    if len(urls) == SIZE:
        break

comment_urls = [url.replace("/article/", "/article/comment/") for url in urls]
session.close()


# 한글 폰트 설정
matplotlib.rc('font', family='NanumGothic')

def get_comment_url(article_url):
    return article_url.replace("/article/", "/article/comment/")

def load_comments(driver, comment_url):
    driver.get(comment_url)
    time.sleep(5)

    # 더보기 반복
    for _ in range(30):
        try:
            more_btn = driver.find_element(By.CLASS_NAME, "u_cbox_btn_more")
            if more_btn.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView(true);", more_btn)
                time.sleep(0.5)
                more_btn.click()
                time.sleep(1.5)
        except:
            break

    all_comments = []
    comment_boxes = driver.find_elements(By.CSS_SELECTOR, "li.u_cbox_comment")

    for box in comment_boxes:
        try:
            nickname = box.find_element(By.CLASS_NAME, "u_cbox_nick").text.strip()
            date = box.find_element(By.CLASS_NAME, "u_cbox_date").text.strip()
            text = box.find_element(By.CLASS_NAME, "u_cbox_contents").text.strip()
            like = int(box.find_element(By.CLASS_NAME, "u_cbox_cnt_recomm").text.strip() or 0)
            dislike = int(box.find_element(By.CLASS_NAME, "u_cbox_cnt_unrecomm").text.strip() or 0)

            all_comments.append({
                "작성자": nickname,
                "작성일자": date,
                "댓글": text,
                "공감수": like,
                "비공감수": dislike,
                "유형": "부모"
            })

            # 답글 열기
            try:
                reply_btn = box.find_element(By.CSS_SELECTOR, "a.u_cbox_reply_btn")
                if reply_btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView(true);", reply_btn)
                    time.sleep(0.3)
                    reply_btn.click()
                    time.sleep(1.0)
            except NoSuchElementException:
                pass

            # 답글 수집
            reply_boxes = box.find_elements(By.CSS_SELECTOR, "ul.u_cbox_reply li.u_cbox_comment")
            for r_box in reply_boxes:
                try:
                    r_nickname = r_box.find_element(By.CLASS_NAME, "u_cbox_nick").text.strip()
                    r_date = r_box.find_element(By.CLASS_NAME, "u_cbox_date").text.strip()
                    r_text = r_box.find_element(By.CLASS_NAME, "u_cbox_contents").text.strip()
                    r_like = int(r_box.find_element(By.CLASS_NAME, "u_cbox_cnt_recomm").text.strip() or 0)
                    r_dislike = int(r_box.find_element(By.CLASS_NAME, "u_cbox_cnt_unrecomm").text.strip() or 0)

                    all_comments.append({
                        "작성자": r_nickname,
                        "작성일자": r_date,
                        "댓글": r_text,
                        "공감수": r_like,
                        "비공감수": r_dislike,
                        "유형": "답글"
                    })
                except NoSuchElementException:
                    continue
        except NoSuchElementException:
            continue
    return all_comments

def analyze_sentiment(comments):
    texts = [c["댓글"] for c in comments]
    classifier = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")
    result_counts = {"긍정적 인식": 0, "부정적 인식": 0, "중립": 0}
    label_map = {
        "1 star": "부정적 인식", "2 stars": "부정적 인식",
        "3 stars": "중립",
        "4 stars": "긍정적 인식", "5 stars": "긍정적 인식"
    }

    for text in texts:
        result = classifier(text)[0]
        sentiment = label_map.get(result["label"], "중립")
        result_counts[sentiment] += 1

    return result_counts

def visualize_sentiment(result_counts, title):
    sizes = list(result_counts.values())
    labels = list(result_counts.keys())
    colors = ["#8fb4eb", "#4E5362", "#b0b1b6"]
    
    if sum(sizes) == 0:
        print(f"⚠️ [{title}] 감정 분석 결과가 없습니다.")
        return

    plt.figure(figsize=(6, 6))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140)
    plt.title(f"[{title}] 댓글 감정 분석 결과")
    plt.axis('equal')
    plt.show()


# 드라이버 설정
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")  # 봇 차단 방지
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=options)

for url in urls:
    comment_url = get_comment_url(url)
    print(f"\n🔗 기사 URL: {url}")

    try:
        comments = load_comments(driver, comment_url)
        print(f"  📥 수집된 댓글 수: {len(comments)}")

        sentiment_results = analyze_sentiment(comments)
        visualize_sentiment(sentiment_results, title=url)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

driver.quit()
