---
name: seo-title-gen
description: 네이버 SEO 블로그 제목 생성. keywords_expanded.json 상위 20개 키워드로 자동완성 키워드를 수집하고, seo-title-generator 에이전트로 제목을 생성합니다. "제목 생성", "SEO 제목", "블로그 제목 만들어줘", "타이틀 생성", "generate titles" 요청 시 사용됩니다.
user-invocable: true
allowed-tools: Read, Bash, Task(seo-title-generator)
---

# SEO 제목 생성 워크플로우

## 개요
keywords_expanded.json에서 상위 20개 키워드를 추출하고, 네이버 자동완성 API로 관련 키워드를 수집한 뒤, seo-title-generator 에이전트에게 제목 생성을 위임합니다.

## 실행 순서

### 0단계: 세션 폴더 생성

```bash
mkdir -p sessions/titles_$(date +%Y%m%d_%H%M%S)
```

생성된 세션 폴더의 절대 경로를 이후 모든 단계에서 사용합니다.

### 1단계: 자동완성 수집

```bash
uv run python autocomplete.py --top 20
```

세션 폴더에 복사:
```bash
cp autocomplete_data.json {세션폴더}/
```

### 2단계: 제목 생성 에이전트 호출

자동완성 수집이 완료되면 seo-title-generator 에이전트를 Task 도구로 호출합니다:

- subagent_type: seo-title-generator
- prompt: "{세션폴더 절대경로}의 autocomplete_data.json 파일을 읽고, 각 키워드의 자동완성 데이터를 활용하여 규칙에 맞는 SEO 제목 20개를 생성해서 {세션폴더 절대경로}/blog_titles.json에 저장해주세요. 제목을 1개 생성할 때마다 즉시 파일에 저장하세요."

### 3단계: 결과 확인

`{세션폴더}/blog_titles.json`을 읽어서 결과를 사용자에게 보여주세요:
- 세션 폴더 경로
- 총 제목 수
- 상위 10개 샘플
- 글자 수 통계 (평균, 최소, 최대)
