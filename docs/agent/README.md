# Claude·Codex 작업 환경

## 구성

| 경로 | 역할 |
| --- | --- |
| `AGENTS.md` | Codex 저장소 진입 지침 |
| `.claude/CLAUDE.md` | 같은 진입·공통·작업 지침을 상대 @ import |
| `docs/agent/common.md`, `workflow.md` | 공통 지침 원본 |
| `docs/agent/subagents/` | planner / implementer / verifier / reviewer 역할 원본 |
| `.claude/agents` | 위 역할 원본으로 연결 |
| `.claude/rules` | 영역별 규칙 원본으로 연결 |
| `.codex/agents` | `docs/agent/adapters/codex`의 TOML로 연결 |

규칙은 연결 경로가 아니라 docs/agent 원본에서 수정한다. 모델·권한·hooks·MCP·동시 실행 수를 강제 설정하지 않는다. 자동 실행·게시·병합·멀티에이전트 강제 정책도 넣지 않았다.

## 사용 예시

- “SPEC-003-WI-01을 읽고 촬영/ROI와 평가 이미지 준비 계획을 정리해줘.”
- “SPEC-002-WI-01 공통 계약을 현재 서버와 대조해서 작성해줘.”
- “reviewer 역할로 이번 변경에서 stale 프레임이 VERIFIED를 만들 수 있는지 검토해줘.”

역할은 단일 세션에서도 사용할 수 있다. 실제 하위 에이전트를 원하면 이를 명시해 요청한다. 미지원 클라이언트에서도 docs의 역할 경로를 직접 읽도록 요청할 수 있다.

## 참고 저장소에서 가져온 것과 뺀 것

[timeCapsule](https://github.com/kjyook/timeCapsule)의 공통 문서 원본·도구별 연결·4역할·기능 스펙/WI/검증 기록·ADR 구조를 RADAR용으로 재작성했다. 제품 요구·기술 스택·긴 승인 양식·develop/squash 정책·항상 직렬/별도 에이전트 실행은 가져오지 않았다.

## 형식 근거와 검증 한계

공식 [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Codex custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Claude memory](https://code.claude.com/docs/en/memory), [Claude subagents](https://code.claude.com/docs/en/sub-agents)를 2026-10-10 확인했다.
프로젝트 Codex 역할 파일은 name/description/developer_instructions, Claude 역할 파일은 YAML name/description과 Markdown 지침을 사용한다. 자동 발견·호출은 클라이언트 버전과 설정에 따라 확인해야 한다. 로컬 codex-cli 0.141.0과 Claude Code 2.1.220을 확인했으며 파일 정합성 검사와 실제 역할 호출 검증은 구분해 아래에 기록한다.

연결을 만든 뒤 새 세션에서 공통 지침을 읽는지 확인한다. Claude에서 첫 agents 디렉터리 생성 후에는 새 세션을 권장한다. 심볼릭 링크를 지원하지 않는 환경에서는 원본 경로를 읽는 작은 참조 파일로 대체하고 두 규칙 사본을 만들지 않는다.

검증 결과는 [설정 검증 기록](validation.md)에 기록한다.
