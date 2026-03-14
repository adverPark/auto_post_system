---
name: publish-cafe
description: 네이버 카페에 pending 포스트를 자동 발행합니다. "카페 발행", "카페에 올려줘", "NCF 발행", "publish cafe", "카페 글 발행" 요청 시 자동 사용됩니다.
user-invocable: true
disable-model-invocation: false
argument-hint: "[프리셋명] [--delay 초] [--schedule]"
allowed-tools: Read, Bash, Agent(cafe-publisher)
---

# 네이버 카페 발행

- 프리셋: $ARGUMENTS (없으면 기본값 사용)

## 중요: 반드시 아래 단계를 순서대로 실행하세요.

## 0단계: 프리셋 결정

`$ARGUMENTS`에서 프리셋명과 옵션을 파싱합니다.

- 프리셋명이 주어지면 해당 프리셋 사용
- 프리셋명이 없으면 `configs/presets.json`을 읽어서 `publish` 값이 `"NCF"`인 프리셋을 자동 선택
- `--delay` 옵션이 있으면 해당 값을 딜레이로 사용 (기본: 5초)
- `--schedule` 옵션이 있거나 사용자가 "스케줄", "예약" 발행을 요청하면 스케줄 모드 사용

## 1단계: 발행 모드 결정

- `--schedule` 옵션이 있거나, 사용자가 "스케줄/예약 발행"을 요청 → **스케줄 모드**
- 그 외 → **즉시 모드** (기존 동작)

## 2단계: cafe-publisher 에이전트 호출

cafe-publisher 에이전트를 Agent 도구로 호출합니다:

**즉시 모드:**
- subagent_type: cafe-publisher
- prompt: "프리셋 '{프리셋명}'으로 네이버 카페에 pending 포스트를 즉시 발행해주세요. 딜레이: {딜레이}초"

**스케줄 모드:**
- subagent_type: cafe-publisher
- prompt: "프리셋 '{프리셋명}'으로 네이버 카페에 pending 포스트를 스케줄 발행해주세요. --schedule 모드로 백그라운드 실행하고, PID와 로그 파일 경로를 알려주세요."

## 3단계: 결과 보고

에이전트의 결과를 사용자에게 전달합니다.

**즉시 모드:**
- 성공 시: 발행된 포스트 목록과 URL
- 실패 시: 에러 내용과 함께 스크린샷 확인 안내
- pending 포스트가 없었을 경우: "발행할 포스트가 없습니다" 보고

**스케줄 모드:**
- 스케줄 발행 시작됨 (PID: xxx)
- 로그 확인: `tail -f logs/schedule_{프리셋명}_xxx.log`
- 모든 포스트 발행 완료 시 자동 종료됨
