---
name: keyword-collect
description: 네이버 연관 키워드를 수집합니다. "키워드 조사", "키워드 수집", "연관 키워드 찾아줘" 요청 시 사용합니다.
user-invocable: true
argument-hint: "<메인 키워드>"
allowed-tools: Read, Bash, Agent(keyword-collector)
---

## 키워드 수집 요청

메인 키워드: $ARGUMENTS

## 실행

keyword-collector 에이전트를 Agent 도구로 호출합니다:

- subagent_type: keyword-collector
- prompt: "$ARGUMENTS 키워드로 연관 키워드를 수집해주세요. 1차 수집(collect.py) → 시드 후보 확인(expand.py --show-candidates) → 시드 선정 및 2차 확장(expand.py --seeds)까지 전부 진행해주세요."

## 결과 보고

에이전트의 결과를 사용자에게 전달합니다:
- 총 수집 키워드 수 (1차 / 2차 / 합계)
- 기회점수 TOP 10 테이블
- 추천 키워드 3~5개
