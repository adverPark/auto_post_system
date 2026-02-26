---
name: keyword-collect
description: 네이버 연관 키워드를 수집합니다. "키워드 조사", "키워드 수집", "연관 키워드 찾아줘" 요청 시 사용합니다.
user-invocable: true
argument-hint: "<메인 키워드>"
---

## 키워드 수집 요청

메인 키워드: $ARGUMENTS

아래 명령어를 실행하여 연관 키워드를 수집하세요:

```bash
uv run python collect.py "$ARGUMENTS"
```

수집 완료 후:
1. `keywords_raw.json` 파일을 읽어 결과 확인
2. 기회점수 상위 10개를 테이블로 보여주기
3. 블로그 글감으로 추천할 키워드 3~5개 선별하여 제안
