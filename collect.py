"""
네이버 연관 키워드 수집기
- 검색광고 API로 연관 키워드 + 검색량 수집
- keywords_raw.json 저장 (스코어 계산은 expand.py에서 최종 수행)

실행: uv run python collect.py "메인키워드"
"""

import sys
import os
import json
import time
import hashlib
import hmac
import base64
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

# ── 환경변수 ──
AD_API_KEY = os.getenv("NAVER_AD_API_KEY")
AD_SECRET_KEY = os.getenv("NAVER_AD_SECRET_KEY")
AD_CUSTOMER_ID = os.getenv("NAVER_AD_CUSTOMER_ID")
SEARCH_CLIENT_ID = os.getenv("NAVER_SEARCH_CLIENT_ID")
SEARCH_CLIENT_SECRET = os.getenv("NAVER_SEARCH_CLIENT_SECRET")

AD_BASE_URL = "https://api.searchad.naver.com"
SEARCH_BASE_URL = "https://openapi.naver.com/v1/search/blog"


def generate_signature(timestamp: str, method: str, path: str) -> str:
    """HMAC-SHA256 서명 생성"""
    message = f"{timestamp}.{method}.{path}"
    sign = hmac.new(
        AD_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(sign).decode("utf-8")


def get_ad_headers(method: str, path: str) -> dict:
    """검색광고 API 인증 헤더"""
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, method, path)
    return {
        "X-Timestamp": timestamp,
        "X-API-KEY": AD_API_KEY,
        "X-Customer": AD_CUSTOMER_ID,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }


def parse_search_count(value) -> int:
    """검색량 파싱: '< 10' → 5, 문자열 → int"""
    if isinstance(value, str):
        if "<" in value:
            return 5
        return int(value.replace(",", ""))
    return int(value) if value else 0


def fetch_related_keywords(keyword: str) -> list[dict]:
    """검색광고 API로 연관 키워드 수집"""
    path = "/keywordstool"
    method = "GET"
    params = {"hintKeywords": keyword, "showDetail": 1}

    headers = get_ad_headers(method, path)
    url = f"{AD_BASE_URL}{path}?{urlencode(params)}"

    print(f"[검색광고 API] '{keyword}' 연관 키워드 조회 중...")

    for attempt in range(3):
        resp = requests.get(url, headers=headers, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            keywords = []
            for item in data.get("keywordList", []):
                pc = parse_search_count(item.get("monthlyPcQcCnt", 0))
                mobile = parse_search_count(item.get("monthlyMobileQcCnt", 0))
                keywords.append({
                    "keyword": item.get("relKeyword", ""),
                    "pc_search": pc,
                    "mobile_search": mobile,
                    "total_search": pc + mobile,
                })
            print(f"  → {len(keywords)}개 키워드 수집 완료")
            return keywords

        if resp.status_code in (429, 500):
            wait = 3 if resp.status_code == 429 else 1
            print(f"  → {resp.status_code} 에러, {wait}초 후 재시도 ({attempt + 1}/3)")
            time.sleep(wait)
            continue

        print(f"  → API 에러: {resp.status_code} {resp.text}")
        return []

    print("  → 최대 재시도 초과")
    return []


def fetch_blog_doc_count(keyword: str) -> int:
    """네이버 검색 API로 블로그 문서 수 조회"""
    headers = {
        "X-Naver-Client-Id": SEARCH_CLIENT_ID,
        "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": 1}

    for attempt in range(3):
        resp = requests.get(SEARCH_BASE_URL, headers=headers, params=params, timeout=10)

        if resp.status_code == 200:
            return resp.json().get("total", 0)

        if resp.status_code in (429, 500):
            wait = 3 if resp.status_code == 429 else 1
            print(f"    → {resp.status_code} 에러, {wait}초 후 재시도 ({attempt + 1}/3)")
            time.sleep(wait)
            continue

        print(f"    → 검색 API 에러: {resp.status_code}")
        return 0

    return 0


def main():
    if len(sys.argv) < 2:
        print("사용법: uv run python collect.py \"메인키워드\"")
        sys.exit(1)

    keyword = sys.argv[1].replace(" ", "")
    print(f"\n{'='*50}")
    print(f"  메인 키워드: {keyword}")
    print(f"{'='*50}\n")

    # 1. 연관 키워드 수집
    keywords = fetch_related_keywords(keyword)
    if not keywords:
        print("연관 키워드를 찾을 수 없습니다.")
        sys.exit(1)

    # 2. 검색량 내림차순 정렬
    keywords.sort(key=lambda x: x["total_search"], reverse=True)

    # 3. JSON 저장
    output_path = "keywords_raw.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"  저장 완료: {output_path} ({len(keywords)}개 키워드)")
    print(f"{'='*50}")

    # 상위 10개 미리보기
    print(f"\n검색량 TOP 10:")
    print(f"{'순위':<4} {'키워드':<20} {'모바일':>8} {'PC':>8} {'합계':>8}")
    print("-" * 44)
    for i, kw in enumerate(keywords[:10]):
        print(f"{i+1:<4} {kw['keyword']:<20} {kw['mobile_search']:>8} {kw['pc_search']:>8} {kw['total_search']:>8}")


if __name__ == "__main__":
    main()
