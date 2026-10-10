# 요구사항 출처와 기능 매핑

## 출처

- 사용자 제공 RADAR 기획안 및 마일스톤: 이 대화에서 2026-10-09 읽음. 개발 09/30–11/16, 중간점검 10/27, 역할은 서비스 개요 참조.
- [Priority별 기능](https://www.notion.so/798536544ad64061abb761d5cb968585): 2026-10-10 브라우저에서 Priority 그룹과 추가 목록을 읽음. 아래는 관찰한 기능명/우선순위의 저장소 작업 대응이며 자동 동기화가 아니다.
- 사용자 제공 교수님 자문 요약: Priority 이후 읽음. 판단 신뢰성·입력 건전성·근거·보류를 핵심 요구로 반영. 자문 문서의 AI 작성 확장 제안/외부 연구 수치는 독립 검증된 사실로 채택하지 않음.
- 현재 구현: 기존 Python PoC와 `8a05c1c`의 파일 이동/검증 근거.

## Priority → workitem

Notion의 상태는 미개발로 표시됐지만 실제 Mock 구현은 존재한다. 아래는 목표 대응이며 해당 기능 전체 완료 표시는 아니다. 한 WI가 여러 기능을 묶으며, 담당·선행·완료 조건은 스펙을 따른다.

| Priority | 기능 | 주 담당 WI |
| --- | --- | --- |
| P0 | 독립 규칙 기반 2차 검증 | [SPEC-005-WI-01](../spec/005-safe-validation.md#wi-01) |
| P0 | 카메라·마이크 입력 건전성 감시 | [SPEC-003-WI-02](../spec/003-cockpit-vision.md#wi-02) |
| P0 | 3상태 판정 및 판단 보류 | [SPEC-005-WI-02](../spec/005-safe-validation.md#wi-02) |
| P0 | 판정 근거 재생·캡처 | [SPEC-006-WI-02](../spec/006-advisory-interface.md#wi-02) |
| P0 | ATC STT 변환 | [SPEC-004-WI-02](../spec/004-speech-communication.md#wi-02) |
| P0 | Resolved 처리 | [SPEC-007-WI-01](../spec/007-closed-loop.md#wi-01) |
| P0 | 음성 경고 | [SPEC-006-WI-03](../spec/006-advisory-interface.md#wi-03) |
| P0 | Error Timeline 생성 | [SPEC-008-WI-02](../spec/008-safety-trace-report.md#wi-02) |
| P0 | Cockpit Setting Error 탐지 | [SPEC-005-WI-02](../spec/005-safe-validation.md#wi-02) |
| P0 | ATC 음성 입력 | [SPEC-004-WI-01](../spec/004-speech-communication.md#wi-01) |
| P0 | Readback STT 변환 | [SPEC-004-WI-02](../spec/004-speech-communication.md#wi-02) |
| P0 | 오류 재검증 | [SPEC-007-WI-01](../spec/007-closed-loop.md#wi-01) |
| P0 | 비행 세션 시작 | [SPEC-006-WI-01](../spec/006-advisory-interface.md#wi-01) |
| P0 | Readback 음성 입력 | [SPEC-004-WI-01](../spec/004-speech-communication.md#wi-01) |
| P0 | 시각 경고 | [SPEC-006-WI-02](../spec/006-advisory-interface.md#wi-02) |
| P0 | Correction Trace 생성 | [SPEC-008-WI-02](../spec/008-safety-trace-report.md#wi-02) |
| P0 | ATC 지시 구조화 | [SPEC-004-WI-02](../spec/004-speech-communication.md#wi-02) |
| P0 | Flight Summary 생성 | [SPEC-008-WI-02](../spec/008-safety-trace-report.md#wi-02) |
| P0 | ATC-Readback 비교 | [SPEC-005-WI-02](../spec/005-safe-validation.md#wi-02) |
| P0 | Safety Trace 저장 | [SPEC-008-WI-01](../spec/008-safety-trace-report.md#wi-01) |
| P0 | Error Classification 생성 | [SPEC-008-WI-02](../spec/008-safety-trace-report.md#wi-02) |
| P0 | 오류 단계 분류 | [SPEC-005-WI-02](../spec/005-safe-validation.md#wi-02) |
| P0 | Readback 정보 구조화 | [SPEC-004-WI-02](../spec/004-speech-communication.md#wi-02) |
| P0 | 비행 종료 | [SPEC-008-WI-03](../spec/008-safety-trace-report.md#wi-03) |
| P0 | Cockpit 설정값 인식 | [SPEC-003-WI-03](../spec/003-cockpit-vision.md#wi-03) |
| P0 | 3단계 교차검증 | [SPEC-005-WI-02](../spec/005-safe-validation.md#wi-02) |
| P0 | Cockpit 영상 입력 | [SPEC-003-WI-02](../spec/003-cockpit-vision.md#wi-02) |
| P0 | 수정값 재인식 | [SPEC-007-WI-02](../spec/007-closed-loop.md#wi-02) |
| P0 | Readback Error 탐지 | [SPEC-005-WI-02](../spec/005-safe-validation.md#wi-02) |
| P1 | 모의비행 교육 모드 | [SPEC-009-WI-02](../spec/009-evaluation-demo.md#wi-02) |
| P1 | 비행 전 시뮬레이션 검증 | [SPEC-009-WI-01](../spec/009-evaluation-demo.md#wi-01) |
| P1 | Communication Uncertainty 통계 | [SPEC-008-WI-02](../spec/008-safety-trace-report.md#wi-02) |
| P1 | AI Confidence 표시 | [SPEC-009-WI-02](../spec/009-evaluation-demo.md#wi-02) |
| P1 | Alert Level 기록 | [SPEC-008-WI-02](../spec/008-safety-trace-report.md#wi-02) |
| P1 | Resolution Time 계산 | [SPEC-008-WI-02](../spec/008-safety-trace-report.md#wi-02) |
| P1 | 불일치 정도 계산 | [SPEC-006-WI-03](../spec/006-advisory-interface.md#wi-03) |
| P1 | 경고 강도 변경 | [SPEC-006-WI-03](../spec/006-advisory-interface.md#wi-03) |
| P1 | 단계별 경고 | [SPEC-006-WI-03](../spec/006-advisory-interface.md#wi-03) |
| P1 | Communication Uncertainty 탐지 | [SPEC-004-WI-03](../spec/004-speech-communication.md#wi-03) |
| P2 | 운항 데이터 기반 모델 성능 평가 | [SPEC-010-WI-02](../spec/010-optional-extensions.md#wi-02) |
| P2 | 리포트 파일 출력 | [SPEC-010-WI-01](../spec/010-optional-extensions.md#wi-01) |

입력 건전성 중 마이크 부분은 SPEC-004-WI-03, 근거 이미지 생성은 SPEC-003-WI-04, Confidence/Quality 생산은 SPEC-002/003/004에서 함께 담당한다. 비행 시작·종료 서버 API는 현재 구현되어 있으나 목표 화면·리포트까지 완료된 것은 아니다.

## 자문 반영과 충돌 처리

- 새 P0 4개: 3상태 판정, 결정론적 2차 검사, 입력 건전성, 근거 패널을 SPEC-002/003/004/005/006에 포함.
- 새 P1 2개: 정답 기반 평가와 모의 교육 피드백을 SPEC-009에 포함.
- 새 P2 1개: 버전별 성능 추세를 SPEC-010에 포함. 실제 비행 자동 재학습/무검증 업데이트는 제외.
- QNH/Baro와 초기 기압 센서 Sensor Cross-Check는 자문 반영으로 제외. 원래 기획의 자동 경고는 재확인용 보조 알림과 억제 정책으로 변경.
- 경보 강화는 검증된 불일치에만 적용하며 낮은 품질/장애를 강한 경고로 승격하지 않음.
- 자문 속 40/200개 데이터·90%·2초·0% 목표는 제안이며 요구 성능으로 확정하지 않음. 거짓 정상과 오류 사례에서의 보류를 별도 측정. 미탐률에 보류를 포함하는지 명시하고 서로 다른 정의를 혼용하지 않음.
- confidence 임계값을 높이면 반드시 오류가 줄어든다고 가정하지 않음. 조정용/평가용 데이터 분리와 calibration 확인이 필요.
- 실제 훈련 비행 shadow mode는 장기 제안이며 이번 실험 범위의 필수 작업으로 넣지 않음.
- 중간점검 품질 요구와 P1 우선순위, SDR 취소선과 후속 SDR 요구는 서비스 개요의 미정 사항으로 유지.
