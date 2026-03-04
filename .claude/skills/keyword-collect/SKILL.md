---
name: keyword-collect
description: 네이버 연관 키워드를 수집합니다. "키워드 조사", "키워드 수집", "연관 키워드 찾아줘" 요청 시 사용합니다.
user-invocable: true
argument-hint: "<메인 키워드>"
---

## 키워드 수집 요청

메인 키워드: $ARGUMENTS

### 1단계: 1차 수집
아래 명령어를 실행하여 연관 키워드를 수집하세요:

```bash
uv run python collect.py "$ARGUMENTS"
```

수집 완료 후:
1. `keywords_raw.json` 파일을 읽어 결과 확인
2. 기회점수 상위 10개를 테이블로 보여주기
3. 블로그 글감으로 추천할 키워드 3~5개 선별하여 제안

### 2단계: 시드 후보 확인
```bash
uv run python expand.py "$ARGUMENTS" --show-candidates
```
모바일 검색량 5,000 이상인 시드 후보 목록을 확인합니다.

### 3단계: 시드 선정 및 2차 확장
후보 중에서 아래 기준으로 최대 5개 시드를 선정합니다:
- 메인 키워드와 다른 주제 (의미적으로 판단)
- 키워드 자체가 블로그 글감이 될 수 있는 것
- 주제 다양성을 고려하여 선택

선정 후 2차 확장 수집 실행:
```bash
uv run python expand.py "$ARGUMENTS" --seeds "시드1,시드2,시드3,시드4,시드5"
```

### 최종 결과
- `keywords_expanded.json` 파일에 1차 + 2차 머지 결과가 저장됩니다
- 기회점수 TOP 10 테이블과 추천 키워드를 보여주세요
