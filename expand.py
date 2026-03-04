"""
네이버 키워드 2차 확장 수집기
- keywords_raw.json (1차 결과)에서 시드 후보 추출
- 시드 키워드로 검색광고 API 2차 수집
- 1차 + 2차 머지 + 중복 제거 → keywords_expanded.json 저장

실행:
  uv run python expand.py "메인키워드" --show-candidates
  uv run python expand.py "메인키워드" --seeds "시드1,시드2,시드3"
"""

import sys
import json
import time
import argparse

from collect import fetch_related_keywords, fetch_blog_doc_count


def load_raw_keywords(path: str = "keywords_raw.json") -> list[dict]:
    """1차 수집 결과 로드"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def show_candidates(raw_keywords: list[dict], main_keyword: str):
    """모바일 검색량 5000+ 시드 후보 출력"""
    candidates = [
        kw for kw in raw_keywords
        if kw["mobile_search"] >= 5000 and kw["keyword"] != main_keyword
    ]
    candidates.sort(key=lambda x: x["total_search"], reverse=True)

    if not candidates:
        print("모바일 검색량 5,000 이상인 후보가 없습니다.")
        return

    print(f"\n{'='*54}")
    print(f"  시드 후보 (모바일 검색량 5,000+, 메인키워드 제외)")
    print(f"{'='*54}")
    print(f"{'#':<4} {'키워드':<24} {'모바일':>8} {'PC':>8} {'합계':>8}")
    print("-" * 54)
    for i, kw in enumerate(candidates, 1):
        print(
            f"{i:<4} {kw['keyword']:<24} {kw['mobile_search']:>8} "
            f"{kw['pc_search']:>8} {kw['total_search']:>8}"
        )
    print(f"\n총 {len(candidates)}개 후보")


def expand_with_seeds(
    raw_keywords: list[dict],
    main_keyword: str,
    seeds: list[str],
):
    """시드 키워드로 2차 확장 수집 후 머지 → 필터 → 스코어 계산"""
    existing_kw_set = {kw["keyword"] for kw in raw_keywords}

    # ── 2차 키워드 수집 (연관 키워드만, 스코어 계산 X) ──
    new_keywords = []
    for seed in seeds:
        seed = seed.strip()
        if not seed:
            continue
        print(f"\n[2차 수집] 시드: {seed}")
        related = fetch_related_keywords(seed)

        # 중복 제거 (1차 + 이미 추가된 2차 키워드)
        fresh = [kw for kw in related if kw["keyword"] not in existing_kw_set]
        print(f"  → 신규 키워드 {len(fresh)}개 (중복 제외)")

        for kw in fresh:
            existing_kw_set.add(kw["keyword"])
            new_keywords.append(kw)

    # ── 1차 + 2차 머지 ──
    merged = raw_keywords + new_keywords
    print(f"\n[머지] 1차: {len(raw_keywords)}개 + 2차: {len(new_keywords)}개 = {len(merged)}개")

    # ── 모바일 검색량 1000 이하 제외 ──
    before_filter = len(merged)
    merged = [kw for kw in merged if kw["mobile_search"] > 1000]
    print(f"[필터] 모바일 검색량 1000 이하 제외: {before_filter}개 → {len(merged)}개")

    # ── 블로그 문서 수 조회 + 기회점수 계산 (최종) ──
    print(f"\n[스코어 계산] {len(merged)}개 키워드 블로그 문서 수 조회 중...")
    for i, kw in enumerate(merged):
        name = kw["keyword"]
        doc_count = fetch_blog_doc_count(name)
        kw["blog_doc_count"] = doc_count
        kw["opportunity_score"] = round(
            kw["total_search"] / (doc_count + 1), 4
        )
        print(
            f"  [{i+1}/{len(merged)}] {name}: "
            f"검색량={kw['total_search']}, 문서수={doc_count}, "
            f"기회점수={kw['opportunity_score']}"
        )
        time.sleep(0.1)

    # ── 기회점수 내림차순 정렬 + 저장 ──
    merged.sort(key=lambda x: x["opportunity_score"], reverse=True)

    output_path = "keywords_expanded.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  최종: {len(merged)}개 → {output_path} 저장 완료")
    print(f"{'='*60}")

    # 상위 10개 미리보기
    print(f"\n기회점수 TOP 10:")
    print(f"{'순위':<4} {'키워드':<24} {'검색량':>8} {'문서수':>8} {'기회점수':>10}")
    print("-" * 58)
    for i, kw in enumerate(merged[:10], 1):
        print(
            f"{i:<4} {kw['keyword']:<24} {kw['total_search']:>8} "
            f"{kw['blog_doc_count']:>8} {kw['opportunity_score']:>10}"
        )


def main():
    parser = argparse.ArgumentParser(description="키워드 2차 확장 수집")
    parser.add_argument("keyword", help="메인 키워드")
    parser.add_argument(
        "--show-candidates",
        action="store_true",
        help="모바일 검색량 5000+ 시드 후보 출력",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        help="쉼표로 구분된 시드 키워드 (예: 재택부업,구글애드센스,단기알바)",
    )
    args = parser.parse_args()

    raw_keywords = load_raw_keywords()
    main_keyword = args.keyword.replace(" ", "")

    if args.show_candidates:
        show_candidates(raw_keywords, main_keyword)
    elif args.seeds:
        seed_list = [s.strip() for s in args.seeds.split(",") if s.strip()]
        if not seed_list:
            print("시드 키워드를 입력하세요.")
            sys.exit(1)
        expand_with_seeds(raw_keywords, main_keyword, seed_list)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
