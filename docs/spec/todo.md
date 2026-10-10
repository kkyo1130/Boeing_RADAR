# RADAR 전체 작업 목록

기준일: 2026-10-10. 현재 dev `9d1d561`에 MCP 정지 이미지 PoC·공유 문서가 병합되어 있다. 이번 태블릿 모의 MCP 화면·Vision 스트림 작업은 dev `9d1d561`에서 만든 `codex/tablet-mcp-stream`에 포함한 변경이다. SPEC-003은 사용자 지정 태블릿 환경을 반영한 v2, 나머지 스펙은 v1이다. 상태는 실제 저장소 근거로 갱신한다.

담당은 기획상 역할 제안이며 세션 배정은 아직 없다. 이 목록은 Git 작업 잠금이 아니다. 착수 전 팀 담당과 공유 상태를 확인한다. 선행 ID의 산출물이 현재 체크아웃에 있어야 한다.

## 권장 진행 순서

1. SPEC-001 실행 기반과 SPEC-002 계약을 먼저 정리한다.
2. 계약이 준비되면 Vision(SPEC-003), 통신·음성(SPEC-004), 서버 판정(SPEC-005), UI(SPEC-006)의 의존성이 없는 WI를 파트별로 진행한다.
3. 10/27 중간점검은 SPEC-009-WI-03으로 통합 검증한다. 이 행의 번호가 뒤에 있어도 후반 작업까지 기다리는 뜻이 아니다.
4. Closed-loop(SPEC-007), Trace/Report(SPEC-008), 평가(SPEC-009)를 최종 기한 전에 통합한다. P2(SPEC-010)는 핵심 안정화 후 수행한다.

| WI·스펙 | 작업 | Priority | 담당 제안 | 선행 WI | 상태 |
| --- | --- | --- | --- | --- | --- |
| [SPEC-001-WI-01](001-development.md#wi-01) | 기존 서버 이동과 디렉터리 골격 | P0 | 공통 | 없음 | done |
| [SPEC-001-WI-02](001-development.md#wi-02) | 파트별 실행·설정·버전 관리 | P0 | 공통 | SPEC-001-WI-01 | pending |
| [SPEC-001-WI-03](001-development.md#wi-03) | 자동 검증 기반과 공유 개발 안내 | P0 | 공통 | SPEC-001-WI-02 | pending |
| [SPEC-002-WI-01](002-observation-contracts.md#wi-01) | 공통 관측·품질·근거 계약 정의 | P0 | 공통 | SPEC-001-WI-01 | implementing |
| [SPEC-002-WI-02](002-observation-contracts.md#wi-02) | 백엔드 수신·지시 연결과 중복/지연 처리 | P0 | 노남경 | SPEC-002-WI-01 | pending |
| [SPEC-002-WI-03](002-observation-contracts.md#wi-03) | 생산자·소비자 계약 통합 검증 | P0 | 공통 | SPEC-002-WI-02 | pending |
| [SPEC-003-WI-01](003-cockpit-vision.md#wi-01) | 정답 영상과 촬영·ROI 설정 | P0 | 김세현 | SPEC-001-WI-01 | implementing |
| [SPEC-003-WI-02](003-cockpit-vision.md#wi-02) | 카메라·파일 입력과 상태 감시 | P0 | 김세현 | SPEC-003-WI-01, SPEC-002-WI-01 | implementing |
| [SPEC-003-WI-03](003-cockpit-vision.md#wi-03) | ALT/HDG 인식·품질·안정화 | P0 | 김세현 | SPEC-003-WI-02 | implementing |
| [SPEC-003-WI-04](003-cockpit-vision.md#wi-04) | 근거 이미지·서버 전송·수정 재관측 | P0 | 김세현 | SPEC-003-WI-03, SPEC-002-WI-02 | pending |
| [SPEC-003-WI-05](003-cockpit-vision.md#wi-05) | Vision 전체 실장비 검증 | P0 | 김세현 | SPEC-003-WI-04 | pending |
| [SPEC-004-WI-01](004-speech-communication.md#wi-01) | 음성 수신·전처리·구간 분리 | P0 | 이예찬 | SPEC-001-WI-01, SPEC-002-WI-01 | pending |
| [SPEC-004-WI-02](004-speech-communication.md#wi-02) | ATC/Pilot STT와 문맥 구조화 | P0 | 노남경 | SPEC-004-WI-01, SPEC-002-WI-02 | pending |
| [SPEC-004-WI-03](004-speech-communication.md#wi-03) | 음성 품질·입력 건전성과 불확실성 | P0/P1 | 이예찬·노남경 | SPEC-004-WI-01, SPEC-004-WI-02 | pending |
| [SPEC-004-WI-04](004-speech-communication.md#wi-04) | 음성 경로 전체 통합 검증 | P0 | 이예찬·노남경 | SPEC-004-WI-02, SPEC-004-WI-03, SPEC-005-WI-02 | pending |
| [SPEC-005-WI-01](005-safe-validation.md#wi-01) | 독립 결정론적 구조화 검사 | P0 | 노남경 | SPEC-002-WI-02 | pending |
| [SPEC-005-WI-02](005-safe-validation.md#wi-02) | NORMAL/MISMATCH/UNVERIFIED와 오류 단계 | P0 | 노남경 | SPEC-005-WI-01 | pending |
| [SPEC-005-WI-03](005-safe-validation.md#wi-03) | 판정 전체 회귀·거짓 정상 확인 | P0 | 노남경 | SPEC-005-WI-02 | pending |
| [SPEC-006-WI-01](006-advisory-interface.md#wi-01) | React 비행 화면·운영 화면과 서버 연결 | P0 | 노남경 | SPEC-002-WI-02 | pending |
| [SPEC-006-WI-02](006-advisory-interface.md#wi-02) | 근거 패널·사용자 확인과 시각 안내 | P0 | 노남경 | SPEC-006-WI-01, SPEC-005-WI-02 | pending |
| [SPEC-006-WI-03](006-advisory-interface.md#wi-03) | 보조 음성·억제 정책과 선택 경고 단계 | P0/P1 | 노남경 | SPEC-006-WI-02 | pending |
| [SPEC-006-WI-04](006-advisory-interface.md#wi-04) | 알림·근거 화면 전체 검증 | P0 | 노남경 | SPEC-006-WI-03, SPEC-003-WI-05, SPEC-004-WI-04 | pending |
| [SPEC-007-WI-01](007-closed-loop.md#wi-01) | Incident·재검증·freshness 정책 | P0 | 노남경 | SPEC-005-WI-03, SPEC-002-WI-02 | pending |
| [SPEC-007-WI-02](007-closed-loop.md#wi-02) | Vision·수정 Readback 재수신 연결 | P0 | 김세현·노남경·이예찬 | SPEC-007-WI-01, SPEC-003-WI-04, SPEC-004-WI-04 | pending |
| [SPEC-007-WI-03](007-closed-loop.md#wi-03) | Closed-loop 전체 시연 검증 | P0 | 공통 | SPEC-007-WI-02, SPEC-006-WI-04 | pending |
| [SPEC-008-WI-01](008-safety-trace-report.md#wi-01) | Safety Trace 확장과 근거 수명주기 | P0 | 노남경 | SPEC-002-WI-02, SPEC-005-WI-02 | pending |
| [SPEC-008-WI-02](008-safety-trace-report.md#wi-02) | Summary·Classification·Timeline·Correction 집계 | P0/P1 | 노남경 | SPEC-008-WI-01, SPEC-007-WI-01 | pending |
| [SPEC-008-WI-03](008-safety-trace-report.md#wi-03) | END FLIGHT 리포트 화면과 기록 조회 | P0 | 노남경 | SPEC-008-WI-02, SPEC-006-WI-01 | pending |
| [SPEC-008-WI-04](008-safety-trace-report.md#wi-04) | 리포트 전체 통합 검증 | P0 | 공통 | SPEC-008-WI-03, SPEC-007-WI-03 | pending |
| [SPEC-009-WI-01](009-evaluation-demo.md#wi-01) | 평가 세트·채점 기준·모델 점수 구분 | P1 | 김세현·노남경·이예찬 | SPEC-003-WI-01, SPEC-002-WI-01 | pending |
| [SPEC-009-WI-02](009-evaluation-demo.md#wi-02) | 파트별·E2E 평가와 모의 교육 피드백 | P1 | 공통 | SPEC-009-WI-01, SPEC-003-WI-05, SPEC-004-WI-04, SPEC-005-WI-03 | pending |
| [SPEC-009-WI-03](009-evaluation-demo.md#wi-03) | 10/27 중간점검 E2E 고정 | P0 | 공통 | SPEC-006-WI-04 | pending |
| [SPEC-009-WI-04](009-evaluation-demo.md#wi-04) | 11/16 최종 QA·인수인계 | P0/P1 | 공통 | SPEC-009-WI-03, SPEC-008-WI-04, SPEC-009-WI-02 | pending |
| [SPEC-010-WI-01](010-optional-extensions.md#wi-01) | 리포트 파일 출력 | P2 | 노남경 | SPEC-008-WI-04 | pending |
| [SPEC-010-WI-02](010-optional-extensions.md#wi-02) | 버전별 모델 평가 추세 | P2 | 공통 | SPEC-009-WI-02 | pending |

## 기존 구현과 이번 계획의 구분

[구현 현황](../IMPLEMENTATION_STATUS.md)에 SPEC별 기존 기반과 남은 범위를 정리했다. 비교·재검증·기본 Trace 등 Mock 서버 기반이 이미 있지만 자문 반영 확장 WI의 전체 완료 조건은 미충족이라 pending을 유지한다. 1/35 done을 제품 완성률로 해석하지 않는다.

## 다음 작업

- 공통: SPEC-002-WI-01 계약을 서버/Vision/통신 담당과 대조한다.
- 세현님: 태블릿용 MCP 화면과 Vision 영상/웹캠·상태 감시·안정화 구현. 다음은 태블릿 실제 프레임 저장→ROI 설정→정답 데이터→가림/끊김/재연결 검증. SPEC-003-WI-01~03은 실제 촬영/공통 계약 AC 미충족으로 implementing 유지. 서버 전송 WI-04는 pending.
- 다른 파트의 작업은 역할 담당과 실제 별도 저장소/미공유 코드 존재 여부를 확인한다.

## 상태 변경 기록

- 2026-10-10 사진 기반 MCP 개선: 기존 참고 사진을 재사용해 실제 조종석 배경·세 숫자 창 오버레이·MCP 확대/전체 보기를 제공. 최종 확대 화면 캡처 실제 OCR 3000/270/250, 변경 3500/0/250, ALT 가림 null 확인. 초기 7세그먼트 오인식 실험은 채택하지 않음. frontend 빌드/브라우저 검증, 실제 태블릿 촬영은 미실행. WI 상태 유지.

- 2026-10-10 태블릿 데모: frontend React MCP, Vision 촬영/ROI 설정·웹캠/영상 입력·상태 감시·연속 안정화 추가. Vision 45개 테스트, frontend 빌드·브라우저 조작, 화면 캡처 OCR 3000/270/250, 무손실 합성 영상 전환/가림/0도/EOF 확인. 실제 태블릿 카메라 및 서버 통합 미실행. SPEC-003 v2와 workitem 기록 갱신; 기존 done 상태 유지. 서버 운영 UI인 SPEC-006-WI-01은 pending 유지.

- 2026-10-10 공유 문서: MCP 원본 사진·최종 ROI/OCR 근거·결과 JSON을 docs/vision에서 안내, 저장소 README 연결. 중복 output 정리. 본 커밋은 에이전트/스펙 문서와 Vision PoC를 포함하며 원격 푸시는 별도다.

- 2026-10-10 HEADING 수정: 방위 창 전처리 후 같은 MCP 사진의 3개 값 10000/270/250 인식 성공. 테스트 29개, 기존 합성 고정 사례 5개 통과. 실제 장비 및 독립 평가 미실행; WI 전체 완료로 변경하지 않음.

- 2026-10-10 MCP 배치: 사용자 지정 고정 지지대/전방 하향 구도 문서화. 새 사진용 3개 ROI·속도 선택 관측 추가, 테스트 20개 통과. OCR 속도 250/ALT 10000; HDG는 문자 오인식으로 null 처리. 실제 장착/카메라 검증 미완료.

- 2026-10-10 참고 화면: 사용자 Cockpit 사진의 HEADING/ALTITUDE 숫자 창 ROI 추가; OCR ALT 10000ft/HDG 272° 수동 대조. 정지 이미지 1개 확인이며 실카메라/바늘 인식 완료 아님.

- 2026-10-10 Vision 착수: 합성 fixture·ROI 설정·정지 이미지 OCR·실패 사유·근거·결과 계약 초안 구현. 13개 테스트와 합성 기대 사례 5개 통과. 003 WI-01~03 / 002 WI-01은 부분 구현 implementing; 전체 AC 완료 아님.

- 2026-10-10 재확인: dev 구조 병합 확인, 기존 테스트 17개 통과, confidence=0/과거 관측 VERIFIED와 null/부분 지시 422 확인. 확장 WI 상태는 유지하고 기존 구현 기반을 별도로 기록.

- 2026-10-10: 최초 계획. 이미 검증·푸시된 구조 WI만 done, 나머지는 pending. 목표·Notion 상태와 실제 구현을 구분함.

- 2026-10-10 커밋 인수인계: `codex/tablet-mcp-stream`에 frontend·Vision 스트림·재현 안내를 함께 보존. 내장/대여 카메라로 촬영 가능 여부를 먼저 확인하고 필요하면 외장 웹캠을 준비한다. 실촬영 기록·검증 순서·서버 연동 선행 조건은 [태블릿 데모 안내](../../vision/docs/tablet-demo.md#6-다음-작업과-기록-방법)를 따른다. 원본 촬영물·출력 로그·빌드 산출물은 커밋에서 제외한다.
