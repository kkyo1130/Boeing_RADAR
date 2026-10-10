# 기능 스펙 안내

기능별 SPEC은 목적·계약·완료 조건, 각 SPEC 내부 WI는 실행 단위, [TODO](todo.md)는 담당·의존성·상태를 관리한다. 문서 작업 요청으로 작성한 초안이며 전체 제품 구현을 요청받았다는 뜻은 아니다.

| 스펙 | Priority | 상태·버전 | WI 수 |
| --- | --- | --- | --- |
| [SPEC-001: 개발 환경과 모노레포 실행](001-development.md) | P0 | draft · v1 | 3 |
| [SPEC-002: 관측 계약과 지시 연결](002-observation-contracts.md) | P0 | draft · v1 | 3 |
| [SPEC-003: Cockpit 영상 관측과 입력 건전성](003-cockpit-vision.md) | P0 | draft · v1 | 5 |
| [SPEC-004: 관제·복명복창 음성 입력과 구조화](004-speech-communication.md) | P0 | draft · v1 | 4 |
| [SPEC-005: 규칙 재검증과 3상태 교차검증](005-safe-validation.md) | P0 | draft · v1 | 3 |
| [SPEC-006: 근거 확인과 시각·음성 보조 알림](006-advisory-interface.md) | P0/P1 | draft · v1 | 4 |
| [SPEC-007: 수정 후 새 관측과 해결 확인](007-closed-loop.md) | P0 | draft · v1 | 3 |
| [SPEC-008: 근거를 포함한 Safety Trace와 비행 리포트](008-safety-trace-report.md) | P0/P1 | draft · v1 | 4 |
| [SPEC-009: 정답 기반 평가·교육 모드·최종 시연](009-evaluation-demo.md) | P0/P1 | draft · v1 | 4 |
| [SPEC-010: 리포트 출력과 버전별 평가 확장](010-optional-extensions.md) | P2 | draft · v1 | 2 |

## 사용 방법

1. TODO에서 할 일을 고르고 해당 SPEC/WI와 선행 결과를 읽는다.
2. 담당·필요 결정·수정 범위를 확인한다. 명확한 사용자 구현 요청은 해당 범위 권한으로 기록하고 반복 승인을 요구하지 않는다.
3. 구현 후 실제 완료 조건을 검증하고 WI 결과·인수인계와 TODO 상태를 갱신한다.
4. 기능의 마지막 통합 WI가 남아 있으면 전체 기능 완료로 보고하지 않는다.

식별자는 `SPEC-NNN`, `SPEC-NNN-WI-NN`, `AC-NN`이다. 순서가 바뀌어도 ID를 바꾸지 않는다. 요구사항·계약·완료 조건 변경은 버전을 올리고 영향을 기록한다. 오탈자·실행 결과 기록은 버전을 올리지 않는다.

[스펙 양식](templates/spec.md), [작업 목록 양식](templates/todo.md), [작업 절차](../agent/workflow.md)를 참고한다. 템플릿의 빈 항목은 실제 구현이나 승인 근거가 아니다.
