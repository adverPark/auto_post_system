---
name: full-pipeline
description: 키워드 조사부터 제목 생성, 캠페인 발행 준비까지 전체 파이프라인을 한번에 실행합니다. "풀파이프라인", "전체 파이프라인", "키워드부터 발행까지", "한번에 돌려줘" 요청 시 사용합니다.
user-invocable: true
disable-model-invocation: true
argument-hint: "<메인키워드> <제목수> <프리셋명>"
allowed-tools: Read, Bash, Task(keyword-collector), Task(seo-title-generator), Task(advercoder-post-generator)
---

# 풀 파이프라인

- 메인 키워드: $0
- 제목(포스트) 수: $1
- 프리셋: $2

## 중요: 반드시 아래 단계를 순서대로 실행하세요.

- 절대 WebSearch, WebFetch 등으로 직접 조사하지 마세요.
- 이 스킬은 서브에이전트에 작업을 위임하는 오케스트레이터입니다.
- 아래 단계 외의 행동은 금지입니다.

## 0단계: 세션 폴더 생성

```bash
mkdir -p sessions/${0}_$(date +%Y%m%d_%H%M%S)
```

생성된 세션 폴더의 **절대 경로**를 이후 모든 단계에서 사용합니다.

## 1단계: 키워드 수집 (keyword-collector 에이전트)

keyword-collector 에이전트를 Task 도구로 호출합니다:

- subagent_type: keyword-collector
- prompt: "$0 키워드로 연관 키워드를 수집해주세요. 1차 수집(collect.py) → 시드 후보 확인(expand.py --show-candidates) → 시드 선정 및 2차 확장(expand.py --seeds)까지 전부 진행해주세요."

완료되면 세션 폴더에 복사:
```bash
cp keywords_raw.json keywords_expanded.json {세션폴더}/
```

## 2단계: 자동완성 수집 + 제목 생성

autocomplete.py를 실행하여 자동완성을 수집합니다:

```bash
uv run python autocomplete.py --top $1
```

세션 폴더에 복사:
```bash
cp autocomplete_data.json {세션폴더}/
```

그 다음 seo-title-generator 에이전트를 Task 도구로 호출합니다:

- subagent_type: seo-title-generator
- prompt: "{세션폴더 절대경로}의 autocomplete_data.json 파일을 읽고, 각 키워드의 자동완성 데이터를 활용하여 규칙에 맞는 SEO 제목 $1개를 생성해서 {세션폴더 절대경로}/blog_titles.json에 저장해주세요. 제목을 1개 생성할 때마다 즉시 파일에 저장하세요."

## 3단계: 캠페인 생성 (advercoder-post-generator 에이전트)

{세션폴더}/blog_titles.json을 Read로 읽어서 titles 문자열을 조합합니다:
- 각 항목의 `title` 필드를 추출
- 제목만 사용 (메인키워드 `///`는 사용자가 명시적으로 요청한 경우에만 붙일 것)
- 줄바꿈(`\n`)으로 연결

advercoder-post-generator 에이전트를 Task 도구로 호출합니다:

- subagent_type: advercoder-post-generator
- prompt: "아래 제목들로 캠페인을 생성해주세요.\n\n프리셋: $2\ntitles:\n{조합된 titles 문자열}"

## 4단계: 최종 결과 보고

사용자에게 아래 정보를 정리해서 보여주세요:

- 세션 폴더 경로
- 수집된 키워드 수 (1차 / 2차 / 합계)
- 생성된 제목 목록 (번호 매기기)
- 캠페인 ID, 상태, 총 포스트 수
- 사용된 프리셋
