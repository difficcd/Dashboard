import urllib.request
import urllib.parse
import json
from collections import defaultdict

# 네이버 API 클라이언트 ID와 시크릿
client_id = "8OABswwfUim7DZvOemS7"
client_secret = "D8vPrxBOM7"

# 법안 키워드 목록, 테스트용도라 5개만 입력했습니다 
law_keywords = ["보건의료기본법", "항공안전법", "디자인보호법", "지방세특례제한법", "전세사기특별법"]

# 뉴스 검색을 위한 기본 URL
base_url = "https://openapi.naver.com/v1/search/news.json"

# 헤더 설정
headers = {
    "X-Naver-Client-Id": client_id,
    "X-Naver-Client-Secret": client_secret
}

# 뉴스 기사를 가져오는 함수
def get_news(query, start):
    url = f"{base_url}?query={urllib.parse.quote(query)}&display=100&start={start}&sort=date"
    request = urllib.request.Request(url, headers=headers)

    response = urllib.request.urlopen(request)
    rescode = response.getcode()

    if rescode == 200:
        response_body = response.read()
        return json.loads(response_body.decode('utf-8'))
    else:
        print(f"⚠️ API 호출 실패: HTTP Error {rescode}")
        return None

# 뉴스 기사에서 키워드 등장 횟수를 계산하는 함수
def count_keywords_in_news(news_items, law_keywords):
    # 뉴스 기사 전체 텍스트 모음
    all_texts = [
        item["title"] + " " + item["description"]
        for item in news_items
    ]
    
    # 키워드별 등장 횟수 세기
    keyword_counts = defaultdict(int)
    for text in all_texts:
        text_lower = text.lower()  # 소문자로 변경하여 대소문자 구분 없앰
        for kw in law_keywords:
            if kw.lower() in text_lower:  # 키워드가 텍스트에 존재하면
                keyword_counts[kw] += text_lower.count(kw.lower())  # 등장 횟수 카운트

    return keyword_counts

# 실시간 뉴스 기반 화제 법안 TOP 5 출력 함수
def display_top_keywords(keyword_counts):
    # 정렬: 등장 횟수 기준 내림차순
    sorted_counts = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)

    # 출력: 결과가 제대로 출력되도록
    print("📊 최근 뉴스 기반 실시간 화제 법안 TOP 5")
    if sorted_counts:
        for i, (kw, count) in enumerate(sorted_counts[:5], 1):
            print(f"{i}. {kw} - 언급 {count}회")
    else:
        print("⚠️ 법안 키워드가 뉴스에 등장하지 않았습니다.")

# 주요 실행 흐름
def main():
    # 5페이지씩 가져와서 뉴스 데이터를 수집
    total_keyword_counts = defaultdict(int)
    for start in range(1, 501, 100):  # 1, 101, 201, 301, 401로 5번 요청, 기본 100개씩 뉴스를 가져오는걸로 설정되어 있어서 5번 요청해서 500개 뉴스 가져옴 
        print(f"📡 {start}번째 뉴스 가져오는 중...")
        result = get_news("법률안", start) # '법률안' 키워드가 있는 최근 뉴스 500개 중에서 검색 (코드 수정하여 가져오는 뉴스기사 개수 조정할 수 있습니다)

        if result and "items" in result:
            news_items = result["items"]
            keyword_counts = count_keywords_in_news(news_items, law_keywords)
            # 각 페이지에서 나온 키워드 등장 횟수 합산
            for kw, count in keyword_counts.items():
                total_keyword_counts[kw] += count

    # 실시간 화제 법안 TOP 5 출력
    display_top_keywords(total_keyword_counts)

# 실행
if __name__ == "__main__":
    main()
