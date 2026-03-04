---
name: keyword-research
description: 네이버 블로그 SEO 키워드 리서치 자동화. 주제를 입력하면 네이버 검색광고 API로 키워드를 수집하고 분석/스코어링하여 블로그 제목까지 생성합니다. "키워드 리서치", "키워드로 제목", "keyword research" 요청 시 사용됩니다.
user-invocable: true
argument-hint: "<메인 키워드>"
allowed-tools: Read, Bash, Task(keyword-collector), Task(seo-title-generator)
---

# 키워드 리서치 → 제목 생성 통합 워크플로우

메인 키워드: $ARGUMENTS

## 중요: 반드시 아래 단계를 순서대로 실행하세요.

- 절대 WebSearch, WebFetch 등으로 직접 조사하지 마세요.
- 이 스킬은 서브에이전트에 작업을 위임하는 오케스트레이터입니다.
- 아래 단계 외의 행동은 금지입니다.

## 0단계: 세션 폴더 생성

작업 시작 전 세션 폴더를 생성합니다:

```bash
mkdir -p sessions/$ARGUMENTS_$(date +%Y%m%d_%H%M%S)
```

생성된 세션 폴더의 절대 경로를 이후 모든 단계에서 사용합니다.

## 1단계: 키워드 수집 (keyword-collector 에이전트)

keyword-collector 에이전트를 Task 도구로 호출합니다:

- subagent_type: keyword-collector
- prompt: "$ARGUMENTS 키워드로 연관 키워드를 수집해주세요. 1차 수집(collect.py) → 시드 후보 확인(expand.py --show-candidates) → 시드 선정 및 2차 확장(expand.py --seeds)까지 전부 진행해주세요."

완료되면 `keywords_expanded.json`이 생성됩니다.

1단계 완료 후 세션 폴더에 복사:
```bash
cp keywords_raw.json keywords_expanded.json {세션폴더}/
```

## 2단계: 자동완성 수집 + 제목 생성

autocomplete.py를 실행하여 자동완성을 수집합니다:

```bash
uv run python autocomplete.py --top 20
```

세션 폴더에 복사:
```bash
cp autocomplete_data.json {세션폴더}/
```

그 다음 seo-title-generator 에이전트를 Task 도구로 호출합니다:

- subagent_type: seo-title-generator
- prompt: "{세션폴더 절대경로}의 autocomplete_data.json 파일을 읽고, 각 키워드의 자동완성 데이터를 활용하여 규칙에 맞는 SEO 제목 20개를 생성해서 {세션폴더 절대경로}/blog_titles.json에 저장해주세요. 제목을 1개 생성할 때마다 즉시 파일에 저장하세요."

## 3단계: 최종 결과 확인

`{세션폴더}/blog_titles.json`을 읽어서 사용자에게 보여주세요:
- 세션 폴더 경로
- 총 제목 수
- 상위 10개 샘플 제목
- 글자 수 통계 (평균, 최소, 최대)
