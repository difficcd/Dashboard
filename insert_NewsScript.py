from bs4 import BeautifulSoup
import requests
import urllib.parse

from dbmanage_News import SessionLocal, BillNews, update_news_body
# 파일 기준 import 경로 조정


def get_article_body(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        article = soup.find("div", id="newsct_article") or soup.find("div", class_="article_body")

        if article:
            # <br>을 줄바꿈으로 바꾸기
            for br in article.find_all("br"):
                br.replace_with("\n")

            # 전체 텍스트 가져오기 (태그 무시)
            text = article.get_text()
            # 연속 개행 정리
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n\n".join(lines)

        return "[본문 없음]"

    except Exception as e:
        return f"[오류: {e}]"




# 본문이 없으면 수집해서 본문을 db에저장, 있으면 skip (선택 자체)
def collect_and_store_missing_bodies(limit: int = 10000):
    session = SessionLocal()
    try:
        # 아직 본문이 없는 뉴스만 선택
        news_entries = (
            session.query(BillNews)
            .filter(BillNews.news_url != "(없음)")
            .filter((BillNews.body == None) | (BillNews.body == ""))
            .limit(limit)
            .all()
        )
        print(f"[INFO] 본문 미수집 뉴스 {len(news_entries)}건 처리 시작")

        for idx, news in enumerate(news_entries, 1):
            raw_url = news.news_url.strip()
            print(f"\n[{idx:03}] {news.news_title}")
            print(f"     URL: {raw_url}")

            body_text = get_article_body(raw_url) # 본문 미수집 뉴스에 대해 처리
            if body_text.startswith("[오류:"):
                print(f"     ❌ 본문 수집 실패: {body_text}")
            else:
                print(f"     ✅ 본문 수집 완료 (길이: {len(body_text)}자)")
                update_news_body(news.bill_id, raw_url, body_text)
    
    finally:
        session.close()


if __name__ == "__main__":
    collect_and_store_missing_bodies() 

