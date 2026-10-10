# 설정·문서 검증 기록

- 날짜: 2026-10-10
- 대상: 에이전트 연결·공통/영역 지침·10개 기능 스펙·35개 WI·TODO·요구사항 매핑.
- 제품 코드 변경: 없음. 새로운 Vision/STT/UI 기능은 구현하거나 실행하지 않았음.

## 파일 검증

- 상대 링크 3개와 Claude @ import 3개 대상 존재 확인.
- Codex TOML 4개 파싱, Claude YAML name/description과 대응 확인.
- 영역 규칙 5개 paths 헤더 확인.
- Markdown 로컬 링크·WI 앵커·AC 대응·TODO 중복/누락·WI 선행 그래프 검사.
- 기존 구조 이동 WI 하나만 done이며 나머지는 pending으로 관리.
- `git diff --check` 수행. 제품 소스는 변경하지 않아 기존 backend 회귀를 반복 실행하지 않음; 기준선 검증은 SPEC-001-WI-01에 보존.

## 실제 클라이언트 확인

- Codex CLI 0.141.0, Claude Code 2.1.220 확인.
- Codex 진입 지침 prompt-input 진단 성공: 모델 입력에 RADAR AGENTS.md 본문과 공통/워크플로우/TODO 참조가 포함됨. 참조된 모든 문서의 자동 로딩이나 사용자 정의 역할 호출을 검증한 것은 아님.
- Codex/Claude 사용자 정의 역할 자동 발견·실제 호출 및 Claude 실제 memory 로딩은 별도 세션으로 검증하지 않음. 형식·링크 검증을 실제 역할 실행 성공으로 해석하지 않음.
- 새 세션에서 AGENTS.md/Claude import를 읽는지 확인하고, 역할 인식이 안 되면 원본 역할 문서를 명시적으로 읽도록 요청.

검사 스크립트는 일회성 임시 도구이며 제품 테스트로 추가하지 않았음. 문서 변경 후 링크·WI 대응·선행 그래프 검사를 다시 수행한다.
