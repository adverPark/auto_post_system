"""
네이버 자동완성 키워드 수집기
- keywords_expanded.json 상위 N개 키워드의 자동완성 수집
- autocomplete_data.json 저장

실행:
  uv run python autocomplete.py              # 상위 100개 (기본값)
  uv run python autocomplete.py --top 50     # 상위 50개
"""

import json
import time
import argparse
import urllib.parse

import requests


def fetch_autocomplete(keyword: str) -> list[str]:
    """네이버 자동완성 API에서 키워드 목록 반환"""
    url = (
        f"https://ac.search.naver.com/nx/ac"
        f"?q={urllib.parse.quote(keyword)}"
        f"&con=1&frm=nv&ans=2&r_format=json&r_enc=UTF-8"
        f"&r_unicode=0&t_koreng=1&q_enc=UTF-8&st=100"
    )
    try:
        data = requests.get(url, timeout=5).json()
        if data.get("items") and data["items"][0]:
            return [item[0] for item in data["items"][0]]
    except Exception:
        pass
    return []


def main():
    parser = argparse.ArgumentParser(description="네이버 자동완성 키워드 수집")
    parser.add_argument(
        "--top",
        type=int,
        default=100,
        help="상위 N개 키워드 (기본값: 100)",
    )
    args = parser.parse_args()

    with open("keywords_expanded.json", "r", encoding="utf-8") as f:
        keywords = json.load(f)[: args.top]

    print(f"\n{'='*50}")
    print(f"  자동완성 수집: 상위 {len(keywords)}개 키워드")
    print(f"{'='*50}\n")

    results = []
    for i, kw_data in enumerate(keywords):
        keyword = kw_data["keyword"]
        autocomplete = fetch_autocomplete(keyword)

        results.append(
            {
                "keyword": keyword,
                "opportunity_score": kw_data.get("opportunity_score", 0),
                "mobile_search": kw_data.get("mobile_search", 0),
                "total_search": kw_data.get("total_search", 0),
                "autocomplete": autocomplete,
            }
        )

        print(f"  [{i+1}/{len(keywords)}] {keyword}: {len(autocomplete)}개 자동완성")
        time.sleep(0.1)

    output_path = "autocomplete_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"  완료: {output_path} 저장 ({len(results)}개)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
