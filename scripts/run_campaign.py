"""애드버코더AI 캠페인 생성 + 폴링 완료 대기 스크립트

Usage:
    # 기본 (INFO, NCF 발행)
    uv run python scripts/run_campaign.py \
        --titles "커피 원두 종류별 특징///커피원두"

    # 여러 포스트
    uv run python scripts/run_campaign.py \
        --titles "제목1///키워드1\n제목2///키워드2"

    # 옵션 지정
    uv run python scripts/run_campaign.py \
        --titles "제목///키워드" \
        --type PARS \
        --name "캠페인명" \
        --model GEMINI30PRO \
        --tone PRF \
        --publish NCF \
        --blog-id 1 \
        --interval 60

    # 블로그/카페 목록 조회
    uv run python scripts/run_campaign.py --list-blogs
"""

import argparse
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://ai.advercoder.com/api/v1"
API_KEY = os.getenv("ADVERCODER_API_KEY")

POLL_INTERVAL = 15  # seconds
POLL_MAX_TRIES = 80  # 15s * 80 = 20min
PRESETS_PATH = os.path.join(os.path.dirname(__file__), "..", "configs", "presets.json")

DEFAULT_PARS_PROMPTS = {
    "researcher": {
        "role": "온라인 자료 검색 및 정보 분석",
        "goal": "정확하고 신뢰할 수 있는 정보 제공",
        "backstory": "당신은 정확하고 신뢰할 수 있는 정보를 제공하는 것을 최우선으로 여깁니다. 다양한 출처를 통해 정보를 수집하고, 항상 사실 확인을 철저히 하여 최신의 정확한 정보만을 제공합니다. url의 끝이 pdf로 끝나는 url은 정보수집에서 제외해 주세요! 팀원들과의 협력을 중요시하며, 귀하의 전문성으로 프로젝트에 기여하고자 합니다.",
    },
    "editor": {
        "role": "독자 친화적이고 정보가 풍부한 한국어 콘텐츠 작성",
        "goal": "추출된 데이터를 정제하고 구조화하여 고품질 데이터셋 생성",
        "backstory": "당신은 독자들이 쉽게 이해하고 공감할 수 있는 콘텐츠를 만듭니다. 정보 전달과 함께 독자의 관심을 끌 수 있는 글쓰기에 능숙합니다. 주요 포털 사이트와 SNS에서 잘 노출될 수 있는 콘텐츠 최적화 능력이 있습니다. 검색 최적화(SEO)를 고려하여 적절한 키워드를 자연스럽게 사용해 주세요. 블로그 포스트는 2000자 이상으로 작성하며, 필요시 마크다운 형식의 링크나 표를 포함해 주세요. 한국인들이 사용하지 않는 단어와 표현을 사용하지 마세요 (영어식 표현.). 이 프로젝트의 중요성을 잘 알고 있으며, 최선을 다해 임하고 있습니다.",
    },
}


def headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def api_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=headers(), params=params)
    r.raise_for_status()
    return r.json()


def api_post(path, data):
    r = requests.post(f"{BASE_URL}{path}", headers=headers(), json=data)
    r.raise_for_status()
    return r.json()


# ── 목록 조회 ──────────────────────────────────────────────

def list_blogs():
    """발행 가능한 블로그/카페 목록 전체 조회"""
    result = {}

    try:
        cafes = api_get("/naver_cafe/cafes/")
        result["naver_cafe"] = cafes if isinstance(cafes, list) else cafes.get("results", cafes)
    except Exception as e:
        result["naver_cafe"] = {"error": str(e)}

    try:
        blogs = api_get("/nblog/blogs/")
        result["naver_blog"] = blogs if isinstance(blogs, list) else blogs.get("results", blogs)
    except Exception as e:
        result["naver_blog"] = {"error": str(e)}

    return result


# ── 캠페인 생성 ────────────────────────────────────────────

def create_campaign(
    titles: str,
    campaign_type: str = "INFO",
    campaign_name: str | None = None,
    model_choice: str = "GEMINI30FLASH",
    tone: str = "FRD",
    publish_status: str = "NCF",
    selected_blog: int | None = None,
    publish_interval: int = 0,
    additional_prompt: str | None = None,
    prompts: dict | None = None,
    image_provider: str = "NOIMG",
    image_size: str = "1024x1024",
    image_mode: str = "THUMB",
    image_count: int = 6,
    max_section_images: int = 4,
    image_prompt_mode: str = "SIMPLE",
    image_additional_prompt: str | None = None,
):
    if not campaign_name:
        first_title = titles.split("\n")[0].split("///")[0][:20]
        campaign_name = f"{first_title} 캠페인"

    # selected_blog 자동 결정
    if publish_status != "DNP" and selected_blog is None:
        blogs = list_blogs()
        if publish_status == "NCF":
            items = blogs.get("naver_cafe", [])
        elif publish_status == "NBL":
            items = blogs.get("naver_blog", [])
        else:
            items = []

        if isinstance(items, list) and len(items) > 0:
            selected_blog = items[0]["id"]
            print(f"[INFO] selected_blog 자동 선택: {selected_blog} ({items[0].get('name', '')})")
        else:
            print("[WARN] 발행 대상 없음 → DNP로 변경")
            publish_status = "DNP"

    from datetime import datetime, timezone, timedelta

    kst = timezone(timedelta(hours=9))
    start_date = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")

    payload = {
        "campaign_name": campaign_name,
        "type": campaign_type,
        "titles": titles,
        "model_choice": model_choice,
        "tone": tone,
        "language": "KO",
        "start_date": start_date,
        "publish_status": publish_status,
        "publish_interval": publish_interval,
    }

    if selected_blog is not None:
        payload["selected_blog"] = selected_blog

    if additional_prompt:
        payload["additional_prompt"] = additional_prompt

    if prompts and campaign_type == "PARS":
        payload["prompts"] = prompts

    # 이미지 설정 (NOIMG가 아닐 때만 포함)
    if image_provider != "NOIMG":
        payload["image_provider"] = image_provider
        payload["image_size"] = image_size
        payload["image_mode"] = image_mode
        payload["image_count"] = image_count
        payload["max_section_images"] = max_section_images
        payload["image_prompt_mode"] = image_prompt_mode
        if image_additional_prompt:
            payload["image_additional_prompt"] = image_additional_prompt

    resp = api_post("/campaigns/", payload)
    return resp


# ── 폴링 ───────────────────────────────────────────────────

def poll_until_complete(campaign_id: int, total_posts: int):
    """캠페인 완료까지 폴링. 완료된 캠페인 상세를 반환."""
    for i in range(1, POLL_MAX_TRIES + 1):
        campaign = api_get(f"/campaigns/{campaign_id}/")
        completed = campaign.get("completed_posts", 0)
        status = campaign.get("status", "")

        # 포스트별 상태 확인 (ERR/CER 감지)
        posts_resp = api_get(f"/campaigns/{campaign_id}/posts/", params={"page_size": 100})
        posts = posts_resp.get("results", [])
        error_posts = [p for p in posts if p.get("status") in ("ERR", "CER")]
        finished_posts = [p for p in posts if p.get("status") in ("COM", "PUB", "ERR", "CER")]

        print(f"[POLL {i}/{POLL_MAX_TRIES}] 완료: {len(finished_posts)}/{total_posts} (성공: {completed}, 에러: {len(error_posts)}, 캠페인: {status})")

        if status == "COM" or len(finished_posts) >= total_posts:
            if error_posts:
                print(f"[WARN] {len(error_posts)}개 포스트 에러 발생:")
                for ep in error_posts:
                    print(f"  - [{ep.get('status')}] {ep.get('title')}: {ep.get('error_message', 'N/A')}")
            return campaign

        time.sleep(POLL_INTERVAL)

    print("[TIMEOUT] 최대 대기 시간 초과")
    return api_get(f"/campaigns/{campaign_id}/")


# ── 결과 수집 ──────────────────────────────────────────────

def get_result_summary(campaign_id: int, publish_status: str, selected_blog: int | None):
    """포스트 목록 + 발행 상태 요약"""
    posts_resp = api_get(f"/campaigns/{campaign_id}/posts/", params={"page_size": 100})
    posts = posts_resp.get("results", [])

    summary = []
    for p in posts:
        summary.append({
            "id": p["id"],
            "title": p["title"],
            "status": p["status"],
            "error_message": p.get("error_message"),
        })

    # 발행 상태 확인
    publish_info = []
    if publish_status == "NCF" and selected_blog:
        try:
            cafe_posts = api_get(f"/naver_cafe/cafes/{selected_blog}/posts/", params={"page_size": 100})
            for cp in cafe_posts.get("results", []):
                publish_info.append({
                    "naver_cafe_post_id": cp["id"],
                    "post_title": cp["post"]["title"],
                    "publish_status": cp["status"],
                })
        except Exception:
            pass
    elif publish_status == "NBL" and selected_blog:
        try:
            blog_posts = api_get(f"/nblog/blogs/{selected_blog}/posts/", params={"page_size": 100})
            for bp in blog_posts.get("results", []):
                publish_info.append({
                    "nblog_post_id": bp["id"],
                    "post_title": bp["post"]["title"],
                    "publish_status": bp["status"],
                })
        except Exception:
            pass

    return {"posts": summary, "publish": publish_info}


# ── 메인 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="애드버코더AI 캠페인 생성 + 완료 대기")
    parser.add_argument("--preset", type=str, default=None, help="프리셋 이름 (configs/presets.json)")
    parser.add_argument("--titles", type=str, help='제목///키워드 (줄바꿈으로 구분)')
    parser.add_argument("--type", type=str, default=None)
    parser.add_argument("--name", type=str, default=None, help="캠페인 이름")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--tone", type=str, default=None)
    parser.add_argument("--publish", type=str, default=None)
    parser.add_argument("--target-id", type=int, default=None, help="발행할 블로그/카페 ID")
    parser.add_argument("--interval", type=int, default=None, help="발행 간격 (시간 단위, 0=즉시, 예: 6=6시간)")
    parser.add_argument("--additional-prompt", type=str, default=None)
    parser.add_argument("--prompts-json", type=str, default=None, help="PARS용 prompts JSON 문자열 또는 파일 경로(@path)")
    parser.add_argument("--image-provider", type=str, default=None, help="이미지 제공자 (NOIMG/OPENAI/GEMINI)")
    parser.add_argument("--image-size", type=str, default=None, help="이미지 크기 (1024x1024 등)")
    parser.add_argument("--image-mode", type=str, default=None, help="이미지 모드 (THUMB/FULL)")
    parser.add_argument("--image-count", type=int, default=None, help="이미지 개수 (0~10)")
    parser.add_argument("--max-section-images", type=int, default=None, help="소제목별 최대 이미지 (1~10)")
    parser.add_argument("--image-prompt-mode", type=str, default=None, help="이미지 프롬프트 방식 (SIMPLE/LLM)")
    parser.add_argument("--image-additional-prompt", type=str, default=None, help="이미지 추가 프롬프트")
    parser.add_argument("--list-blogs", action="store_true", help="블로그/카페 목록 조회만")
    parser.add_argument("--list-presets", action="store_true", help="프리셋 목록 조회")
    parser.add_argument("--no-poll", action="store_true", help="캠페인 생성만 하고 폴링 안 함")

    args = parser.parse_args()

    if not API_KEY:
        print(json.dumps({"error": "ADVERCODER_API_KEY not found in .env"}))
        sys.exit(1)

    # 프리셋 목록 조회
    if args.list_presets:
        try:
            with open(PRESETS_PATH, encoding="utf-8") as f:
                presets = json.load(f)
            for name, cfg in presets.items():
                desc = cfg.get("description", "")
                print(f"  [{name}] {desc}")
        except FileNotFoundError:
            print("[ERROR] configs/presets.json 파일 없음")
        return

    # 프리셋 로드 → CLI 옵션으로 오버라이드
    preset = {}
    if args.preset:
        try:
            with open(PRESETS_PATH, encoding="utf-8") as f:
                presets = json.load(f)
        except FileNotFoundError:
            print(f"[ERROR] configs/presets.json 파일 없음")
            sys.exit(1)

        if args.preset not in presets:
            print(f"[ERROR] 프리셋 '{args.preset}' 없음. 사용 가능: {', '.join(presets.keys())}")
            sys.exit(1)

        preset = presets[args.preset]
        print(f"[INFO] 프리셋 '{args.preset}' 로드: {preset.get('description', '')}")

    # 프리셋 기본값 ← CLI 오버라이드
    campaign_type = args.type or preset.get("type", "INFO")
    model = args.model or preset.get("model", "GEMINI30FLASH")
    tone = args.tone or preset.get("tone", "FRD")
    publish = args.publish or preset.get("publish", "NCF")
    target_id = args.target_id if args.target_id is not None else preset.get("target_id")
    interval = args.interval if args.interval is not None else preset.get("interval", 0)

    if interval > 720:  # 30일 이상이면 경고
        print(f"[WARN] interval={interval}시간({interval // 24}일)은 비정상적으로 큽니다. "
              f"단위는 '시간'입니다 (예: 6=6시간). '분' 단위가 아닌지 확인하세요.")

    # 이미지 설정: CLI > 프리셋 > 기본값
    image_provider = args.image_provider or preset.get("image_provider", "NOIMG")
    image_size = args.image_size or preset.get("image_size", "1024x1024")
    image_mode = args.image_mode or preset.get("image_mode", "THUMB")
    image_count = args.image_count if args.image_count is not None else preset.get("image_count", 6)
    max_section_images = args.max_section_images if args.max_section_images is not None else preset.get("max_section_images", 4)
    image_prompt_mode = args.image_prompt_mode or preset.get("image_prompt_mode", "SIMPLE")
    image_additional_prompt = args.image_additional_prompt or preset.get("image_additional_prompt")

    # 목록 조회 모드
    if args.list_blogs:
        result = list_blogs()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not args.titles:
        parser.error("--titles is required (unless --list-blogs)")

    # titles의 리터럴 \n을 실제 줄바꿈으로 변환
    titles = args.titles.replace("\\n", "\n")

    # prompts 결정: CLI > 프리셋 > 디폴트
    prompts = None
    if args.prompts_json:
        if args.prompts_json.startswith("@"):
            with open(args.prompts_json[1:]) as f:
                prompts = json.load(f)
        else:
            prompts = json.loads(args.prompts_json)
    elif preset.get("prompts"):
        prompts = preset["prompts"]
        print("[INFO] 프리셋 프롬프트 사용")

    if campaign_type == "PARS" and prompts is None:
        prompts = DEFAULT_PARS_PROMPTS
        print("[INFO] PARS 디폴트 프롬프트 사용")

    # 1. 캠페인 생성
    print(f"[START] 캠페인 생성 중...")
    campaign = create_campaign(
        titles=titles,
        campaign_type=campaign_type,
        campaign_name=args.name,
        model_choice=model,
        tone=tone,
        publish_status=publish,
        selected_blog=target_id,
        publish_interval=interval,
        additional_prompt=args.additional_prompt,
        prompts=prompts,
        image_provider=image_provider,
        image_size=image_size,
        image_mode=image_mode,
        image_count=image_count,
        max_section_images=max_section_images,
        image_prompt_mode=image_prompt_mode,
        image_additional_prompt=image_additional_prompt,
    )

    campaign_id = campaign["id"]
    total_posts = campaign["total_posts"]
    selected_blog = campaign.get("nblog") or target_id
    publish_status = publish

    print(f"[OK] 캠페인 생성 완료: id={campaign_id}, total_posts={total_posts}")

    if args.no_poll:
        print(json.dumps({"campaign_id": campaign_id, "total_posts": total_posts}, indent=2))
        return

    # 2. 폴링
    final_campaign = poll_until_complete(campaign_id, total_posts)

    # 3. 결과 요약
    result_summary = get_result_summary(campaign_id, publish_status, selected_blog)

    output = {
        "campaign_id": campaign_id,
        "campaign_name": final_campaign.get("campaign_name"),
        "type": final_campaign.get("type"),
        "status": final_campaign.get("status"),
        "total_posts": total_posts,
        "completed_posts": final_campaign.get("completed_posts", 0),
        **result_summary,
    }

    print("\n[RESULT]")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
