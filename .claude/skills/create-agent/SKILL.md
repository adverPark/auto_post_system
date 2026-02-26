---
name: create-agent
description: 새로운 서브에이전트를 생성합니다. "에이전트 만들어줘", "서브에이전트 추가" 요청 시 사용합니다.
user-invocable: true
argument-hint: "<에이전트 이름> <설명>"
---

## 서브에이전트 생성 요청

사용자 요청: $ARGUMENTS

아래 절차에 따라 새로운 서브에이전트를 생성하세요:

### 1단계: 요구사항 분석
- 에이전트 이름 결정 (소문자+하이픈만 허용, 예: `code-reviewer`)
- 목적과 역할 정의
- 필요한 도구 결정 (최소 권한 원칙: 필요한 도구만 포함)
- 적합한 모델 선택 (간단한 작업=haiku, 일반=sonnet, 복잡=opus)

### 2단계: 중복 확인
- `.claude/agents/` 에 같은 이름이 있는지 Glob으로 확인
- 이미 존재하면 사용자에게 덮어쓸지 확인

### 3단계: 파일 생성
- 디렉토리 생성: `mkdir -p .claude/agents/<name>/`
- 파일 위치: `.claude/agents/<name>/AGENT.md`
- YAML 프론트매터 + 마크다운 프롬프트 본문

### YAML 프론트매터 필드 레퍼런스

```yaml
---
name: <소문자-하이픈>           # 필수
description: <구체적 설명>       # 필수 - 역할 + 트리거 키워드 포함
tools: Read, Grep, Glob, Bash   # 선택 (기본: 모든 도구 상속)
model: sonnet|opus|haiku|inherit # 선택 (기본: inherit)
maxTurns: 10                     # 선택: API 라운드트립 최대 횟수
skills:                          # 선택: 미리 로드할 스킬
  - skill-name
memory: user|project|local       # 선택: 영구 메모리 활성화
background: false                # 선택: true면 항상 백그라운드 실행
isolation: worktree              # 선택: 독립 git worktree에서 실행
permissionMode: default          # 선택: default|acceptEdits|dontAsk|bypassPermissions|plan
hooks:                           # 선택: 라이프사이클 훅
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate.sh"
mcpServers:                      # 선택: MCP 서버 설정
  server-name: {}
---
```

### 프롬프트 본문 작성법
1. **역할 정의**: "당신은 ~하는 전문가입니다" 로 시작
2. **구체적 절차**: 번호 매기기로 단계별 수행 내용
3. **출력 형식**: 기대하는 결과물의 형태를 지정
4. **제약 조건**: 하지 말아야 할 것을 명확히 명시

### 완성 예제

```markdown
---
name: code-reviewer
description: 코드 리뷰 전문가. 코드 작성/수정 후 품질, 보안, 성능을 검토합니다. "코드 리뷰해줘", "리뷰", "코드 검토" 요청 시 자동 사용됩니다.
tools: Read, Grep, Glob
model: sonnet
---

당신은 시니어 코드 리뷰어입니다.

## 절차
1. git diff로 최근 변경사항 확인
2. 변경된 파일에 집중하여 리뷰

## 체크리스트
- 코드 가독성과 네이밍
- 중복 코드 여부
- 에러 핸들링
- 보안 취약점 (API 키 노출, 인젝션 등)
- 성능 고려사항

## 출력 형식
- Critical (반드시 수정)
- Warning (수정 권장)
- Suggestion (개선 제안)
```

### 4단계: 결과 보고
- 생성된 파일 경로
- 에이전트 이름과 설명
- 사용 가능한 도구 목록
- 호출 방법: Claude가 자동 위임하거나 사용자가 명시적으로 요청
