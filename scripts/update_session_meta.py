"""session_meta.json 업데이트 헬퍼.

Usage:
    uv run python scripts/update_session_meta.py {SESSION_DIR} \
        --set "progress.keyword_collect.status" "completed" \
        --set-now "progress.keyword_collect.completed_at"
"""

import argparse
import json
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def update_meta(session_dir: str, sets: list, set_nows: list):
    path = f"{session_dir}/session_meta.json"
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)

    def set_nested(obj, dotted_key, value):
        parts = dotted_key.split(".")
        for part in parts[:-1]:
            obj = obj[part]
        obj[parts[-1]] = value

    now = datetime.now(KST).isoformat()

    for key, value in sets:
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed = value
        set_nested(meta, key, parsed)

    for key in set_nows:
        set_nested(meta, key, now)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[META] {path} 업데이트 완료")


def main():
    parser = argparse.ArgumentParser(description="session_meta.json 업데이트")
    parser.add_argument("session_dir", help="세션 디렉토리 경로")
    parser.add_argument(
        "--set", nargs=2, action="append", default=[], metavar=("KEY", "VALUE"),
        help="key.path value 형식으로 값 설정",
    )
    parser.add_argument(
        "--set-now", action="append", default=[], metavar="KEY",
        help="key.path에 현재 시각(KST) 설정",
    )
    parser.add_argument(
        "--init", action="store_true",
        help="초기 session_meta.json 생성",
    )
    parser.add_argument("--keyword", default=None)
    parser.add_argument("--preset", default=None)
    parser.add_argument("--title-count", type=int, default=None)
    args = parser.parse_args()

    if args.init:
        now = datetime.now(KST).isoformat()
        import os
        meta = {
            "keyword": args.keyword or "",
            "preset": args.preset or "",
            "title_count": args.title_count or 0,
            "created_at": now,
            "session_dir": os.path.abspath(args.session_dir),
            "campaign_id": None,
            "publisher_pid": None,
            "publisher_log": None,
            "progress": {
                "keyword_collect": {"status": "pending", "completed_at": None},
                "autocomplete": {"status": "pending", "completed_at": None},
                "title_generation": {"status": "pending", "completed_at": None},
                "campaign_creation": {"status": "pending", "completed_at": None, "campaign_id": None},
                "cafe_publish": {"status": "pending", "started_at": None, "pid": None, "log": None},
            },
        }
        path = f"{args.session_dir}/session_meta.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"[META] {path} 초기화 완료")
        return

    update_meta(args.session_dir, args.set, args.set_now)


if __name__ == "__main__":
    main()
