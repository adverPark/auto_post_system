---
name: create-skill
description: 새로운 스킬(슬래시 커맨드)을 생성합니다. "스킬 만들어줘", "커맨드 추가", "슬래시 명령어 생성" 요청 시 사용합니다.
user-invocable: true
argument-hint: "<스킬 이름> <설명>"
---

## 스킬 생성 요청

사용자 요청: $ARGUMENTS

아래 절차에 따라 새로운 스킬을 생성하세요:

### 1단계: 요구사항 분석
- 스킬 이름 결정 (소문자+하이픈, `/name`으로 호출됨)
- 목적과 용도 정의
- 호출 방식 결정:
  - `user-invocable: true` + `disable-model-invocation: true` → `/명령어`로만 호출
  - `user-invocable: true` (disable 미설정) → `/명령어` + Claude 자동 호출
  - `user-invocable: false` → Claude 자동 호출만 (레퍼런스용)
- 인수 필요 여부 결정

### 2단계: 중복 확인
- `.claude/skills/` 에 같은 이름이 있는지 Glob으로 확인
- 이미 존재하면 사용자에게 덮어쓸지 확인

### 3단계: 파일 생성
- 디렉토리 생성: `mkdir -p .claude/skills/<name>/`
- 파일 위치: `.claude/skills/<name>/SKILL.md`

### YAML 프론트매터 필드 레퍼런스

```yaml
---
name: <소문자-하이픈>                    # 슬래시 커맨드 이름 (/name)
description: <구체적 설명>                # Claude 자동 판단 기준
user-invocable: true                     # true = /명령어 사용 가능
disable-model-invocation: true           # true = /명령어로만 호출 (Claude 자동 호출 차단)
argument-hint: "[인수 설명]"              # 자동완성 시 표시되는 힌트
allowed-tools: Read, Grep, Glob          # 스킬 실행 시 사용 가능한 도구 제한
model: sonnet|opus|haiku                 # 모델 지정
context: fork                            # fork = 별도 에이전트에서 실행 (메인 컨텍스트 격리)
agent: Explore                           # context: fork일 때만 사용, 실행할 에이전트 타입
hooks:                                   # 선택: 라이프사이클 훅
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate.sh"
---
```

### 필드 간 관계

| 설정 조합 | 결과 |
|-----------|------|
| `user-invocable: true` | `/name`으로 호출 가능 + Claude 자동 호출 가능 |
| `user-invocable: true` + `disable-model-invocation: true` | `/name`으로만 호출 (Claude 자동 호출 차단) |
| `user-invocable: false` 또는 미설정 | Claude만 자동 호출 (슬래시 커맨드 비활성) |
| `context: fork` | 별도 에이전트에서 실행 (큰 출력 격리에 유용) |
| `context: fork` + `agent: <name>` | 특정 서브에이전트에서 실행 |

### 특수 변수 & 동적 컨텍스트

| 문법 | 설명 | 예시 |
|------|------|------|
| `$ARGUMENTS` | 슬래시 커맨드 뒤의 전체 텍스트 | `/deploy production` → `production` |
| `$0`, `$1`, `$2` | 개별 인수 (공백 구분) | `/migrate Button React Vue` → $0=Button |
| `` !`command` `` | 스킬 로드 시 셸 명령 실행 결과로 대체 | `` !`git branch --show-current` `` → `main` |

### 완성 예제

```markdown
---
name: deploy
description: 애플리케이션을 배포합니다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[staging|production]"
---

## 배포 요청

환경: $ARGUMENTS (비어있으면 staging)

현재 상태:
- 브랜치: !`git branch --show-current`
- 최근 커밋: !`git log --oneline -3`

## 절차
1. 현재 브랜치가 main인지 확인
2. 테스트 실행
3. 빌드
4. $ARGUMENTS 환경에 배포
5. 배포 확인
```

### 4단계: 결과 보고
- 생성된 파일 경로
- 슬래시 커맨드: `/name`
- 호출 방식 (수동/자동/둘다)
- 사용 예시
- 인수 설명
