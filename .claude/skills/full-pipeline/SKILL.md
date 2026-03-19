---
name: full-pipeline
description: 키워드 조사부터 제목 생성, 캠페인 발행 준비, 카페 자동 발행까지 전체 파이프라인을 한번에 실행합니다. "풀파이프라인", "전체 파이프라인", "키워드부터 발행까지", "한번에 돌려줘" 요청 시 사용합니다.
user-invocable: true
disable-model-invocation: true
argument-hint: "<메인키워드> <제목수> <프리셋명>"
allowed-tools: Read, Bash, Agent(keyword-collector), Agent(seo-title-generator), Agent(advercoder-post-generator), Agent(cafe-publisher)
---

# 풀 파이프라인

- 메인 키워드: $0
- 제목(포스트) 수: $1
- 프리셋: $2

## 중요: 반드시 아래 단계를 순서대로 실행하세요.

- 절대 WebSearch, WebFetch 등으로 직접 조사하지 마세요.
- 이 스킬은 서브에이전트에 작업을 위임하는 오케스트레이터입니다.
- 아래 단계 외의 행동은 금지입니다.
- `{SESSION_DIR}`은 0단계에서 생성된 세션 폴더의 **절대 경로**로 대체하세요.

## 0단계: 세션 폴더 생성 + session_meta.json 초기화

```bash
SESSION_DIR="sessions/${0}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SESSION_DIR"
echo "세션 폴더: $(cd "$SESSION_DIR" && pwd)"
```

생성된 세션 폴더의 **절대 경로**를 이후 모든 단계에서 `{SESSION_DIR}`로 사용합니다.

session_meta.json을 초기화합니다:
```bash
uv run python scripts/update_session_meta.py {SESSION_DIR} \
  --init --keyword "$0" --preset "$2" --title-count $1
```

## 1단계: 키워드 수집 (keyword-collector 에이전트)

keyword-collector 에이전트를 Agent 도구로 호출합니다:

- subagent_type: keyword-collector
- prompt: "$0 키워드로 연관 키워드를 수집해주세요. 1차 수집(collect.py) → 시드 후보 확인(expand.py --show-candidates) → 시드 선정 및 2차 확장(expand.py --seeds)까지 전부 진행해주세요."

완료되면 세션 폴더에 복사 + session_meta 업데이트:
```bash
cp keywords_raw.json keywords_expanded.json {SESSION_DIR}/
uv run python scripts/update_session_meta.py {SESSION_DIR} \
  --set "progress.keyword_collect.status" "completed" \
  --set-now "progress.keyword_collect.completed_at"
```

## 2단계: 자동완성 수집 + 제목 생성

autocomplete.py를 실행하여 자동완성을 수집합니다:

```bash
uv run python autocomplete.py --top $1
cp autocomplete_data.json {SESSION_DIR}/
uv run python scripts/update_session_meta.py {SESSION_DIR} \
  --set "progress.autocomplete.status" "completed" \
  --set-now "progress.autocomplete.completed_at"
```

그 다음 seo-title-generator 에이전트를 Agent 도구로 호출합니다:

- subagent_type: seo-title-generator
- prompt: "{SESSION_DIR}의 autocomplete_data.json 파일을 읽고, 각 키워드의 자동완성 데이터를 활용하여 규칙에 맞는 SEO 제목 $1개를 생성해서 {SESSION_DIR}/blog_titles.json에 저장해주세요. 제목을 1개 생성할 때마다 즉시 파일에 저장하세요."

완료 후 session_meta 업데이트:
```bash
uv run python scripts/update_session_meta.py {SESSION_DIR} \
  --set "progress.title_generation.status" "completed" \
  --set-now "progress.title_generation.completed_at"
```

## 3단계: 캠페인 생성 (advercoder-post-generator 에이전트)

{SESSION_DIR}/blog_titles.json을 Read로 읽어서 titles 문자열을 조합합니다:
- 각 항목의 `title` 필드를 추출
- 제목만 사용 (메인키워드 `///`는 사용자가 명시적으로 요청한 경우에만 붙일 것)
- 줄바꿈(`\n`)으로 연결

advercoder-post-generator 에이전트를 Agent 도구로 호출합니다:

- subagent_type: advercoder-post-generator
- prompt: "아래 제목들로 캠페인을 생성해주세요.\n\n프리셋: $2\ntitles:\n{조합된 titles 문자열}"

완료 후 session_meta 업데이트 (캠페인 결과에서 campaign_id를 추출):
```bash
uv run python scripts/update_session_meta.py {SESSION_DIR} \
  --set "campaign_id" "{campaign_id}" \
  --set "progress.campaign_creation.status" "completed" \
  --set-now "progress.campaign_creation.completed_at" \
  --set "progress.campaign_creation.campaign_id" "{campaign_id}"
```

## 4단계: 카페 자동 발행 (cafe-publisher 에이전트)

프리셋의 `publish` 값이 `"NCF"`인 경우, 캠페인의 글 작성이 완료된 후 카페에 자동 발행합니다.

**4-1. 글 작성 완료 대기**

3단계의 advercoder-post-generator가 캠페인 글 작성 완료를 확인한 뒤 진행합니다.
(advercoder-post-generator는 내부적으로 폴링하여 완료를 대기합니다)

**4-2. cafe-publisher 에이전트 호출**

cafe-publisher 에이전트를 Agent 도구로 호출합니다:

- subagent_type: cafe-publisher
- prompt: "프리셋 '$2'로 네이버 카페에 pending 포스트를 발행해주세요. PID와 로그 파일 경로를 알려주세요."

**4-3. session_meta 업데이트**

cafe-publisher의 결과에서 PID와 로그 경로를 추출하여 업데이트:
```bash
uv run python scripts/update_session_meta.py {SESSION_DIR} \
  --set "publisher_pid" "{PID}" \
  --set "publisher_log" "{로그파일경로}" \
  --set "progress.cafe_publish.status" "in_progress" \
  --set-now "progress.cafe_publish.started_at" \
  --set "progress.cafe_publish.pid" "{PID}" \
  --set "progress.cafe_publish.log" "{로그파일경로}"
```

## 5단계: 최종 결과 보고

사용자에게 아래 정보를 정리해서 보여주세요:

- 세션 폴더 경로
- 수집된 키워드 수 (1차 / 2차 / 합계)
- 생성된 제목 목록 (번호 매기기)
- 캠페인 ID, 상태, 총 포스트 수
- 카페 발행: 백그라운드 실행 중 (PID: xxx, 로그: logs/publish_xxx.log)
- 사용된 프리셋
- 세션 상태 확인: `cat {SESSION_DIR}/session_meta.json`
