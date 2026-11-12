# RADAR 전체 작업 목록

기준일: 2026-10-18. PR #13 리뷰3건 수정 후 squash merge한 dev(`ba2dc65`) 기준이다. WI-02 done, SPEC-006-WI-03 음성·억제 정책을 전용 PR reviewing으로 제출한다. 다른 WI 상태는 유지한다.

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
| [SPEC-002-WI-01](002-observation-contracts.md#wi-01) | 공통 관측·품질·근거 계약 정의 | P0 | 공통 | SPEC-001-WI-01 | done |
| [SPEC-002-WI-02](002-observation-contracts.md#wi-02) | 백엔드 수신·지시 연결과 중복/지연 처리 | P0 | 노남경 | SPEC-002-WI-01 | done |
| [SPEC-002-WI-03](002-observation-contracts.md#wi-03) | 생산자·소비자 계약 통합 검증 | P0 | 공통 | SPEC-002-WI-02 | done |
| [SPEC-003-WI-01](003-cockpit-vision.md#wi-01) | 정답 영상과 촬영·ROI 설정 | P0 | 김세현 | SPEC-001-WI-01 | implementing |
| [SPEC-003-WI-02](003-cockpit-vision.md#wi-02) | 카메라·파일 입력과 상태 감시 | P0 | 김세현 | SPEC-003-WI-01, SPEC-002-WI-01 | implementing |
| [SPEC-003-WI-03](003-cockpit-vision.md#wi-03) | ALT/HDG 인식·품질·안정화 | P0 | 김세현 | SPEC-003-WI-02 | implementing |
| [SPEC-003-WI-04](003-cockpit-vision.md#wi-04) | 근거 이미지·서버 전송·수정 재관측 | P0 | 김세현 | SPEC-003-WI-03, SPEC-002-WI-02 | pending |
| [SPEC-003-WI-05](003-cockpit-vision.md#wi-05) | Vision 전체 실장비 검증 | P0 | 김세현 | SPEC-003-WI-04 | pending |
| [SPEC-004-WI-01](004-speech-communication.md#wi-01) | 음성 수신·전처리·구간 분리 | P0 | 이예찬 | SPEC-001-WI-01, SPEC-002-WI-01 | pending |
| [SPEC-004-WI-02](004-speech-communication.md#wi-02) | ATC/Pilot STT와 문맥 구조화 | P0 | 노남경 | SPEC-004-WI-01, SPEC-002-WI-02 | reviewing |
| [SPEC-004-WI-03](004-speech-communication.md#wi-03) | 음성 품질·입력 건전성과 불확실성 | P0/P1 | 이예찬·노남경 | SPEC-004-WI-01, SPEC-004-WI-02 | pending |
| [SPEC-004-WI-04](004-speech-communication.md#wi-04) | 음성 경로 전체 통합 검증 | P0 | 이예찬·노남경 | SPEC-004-WI-02, SPEC-004-WI-03, SPEC-005-WI-02 | pending |
| [SPEC-005-WI-01](005-safe-validation.md#wi-01) | 독립 결정론적 구조화 검사 | P0 | 노남경 | SPEC-002-WI-02 | done |
| [SPEC-005-WI-02](005-safe-validation.md#wi-02) | NORMAL/MISMATCH/UNVERIFIED와 오류 단계 | P0 | 노남경 | SPEC-005-WI-01 | done |
| [SPEC-005-WI-03](005-safe-validation.md#wi-03) | 판정 전체 회귀·거짓 정상 확인 | P0 | 노남경 | SPEC-005-WI-02 | done |
| [SPEC-006-WI-01](006-advisory-interface.md#wi-01) | React 비행 화면·운영 화면과 서버 연결 | P0 | 노남경 | SPEC-002-WI-02 | done |
| [SPEC-006-WI-02](006-advisory-interface.md#wi-02) | 근거 패널·사용자 확인과 시각 안내 | P0 | 노남경 | SPEC-006-WI-01, SPEC-005-WI-02 | done |
| [SPEC-006-WI-03](006-advisory-interface.md#wi-03) | 보조 음성·억제 정책과 선택 경고 단계 | P0/P1 | 노남경 | SPEC-006-WI-02 | reviewing |
| [SPEC-006-WI-04](006-advisory-interface.md#wi-04) | 알림·근거 화면 전체 검증 | P0 | 노남경 | SPEC-006-WI-03, SPEC-003-WI-05, SPEC-004-WI-04 | pending |
| [SPEC-007-WI-01](007-closed-loop.md#wi-01) | Incident·재검증·freshness 정책 | P0 | 노남경 | SPEC-005-WI-03, SPEC-002-WI-02 | done |
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

[구현 현황](../IMPLEMENTATION_STATUS.md)에 SPEC별 기존 기반과 남은 범위를 정리했다. 비교·재검증·기본 Trace 등 Mock 서버 기반이 이미 있지만 자문 반영 확장 WI의 전체 완료 조건은 미충족이라 pending을 유지한다. 10/35 done을 제품 완성률로 해석하지 않는다.

## 다음 작업

- UI: SPEC-006-WI-03 PR 리뷰 후 실제 PTT/ATC·카메라 생산자와 연결해 WI-04 전체 인수를 진행한다. SPEC-007-WI-02 실제 수정 입력 연결은 SPEC-003-WI-04·SPEC-004-WI-04가 더 필요하다.
- 세현님: 태블릿용 MCP 화면과 Vision 영상/웹캠·상태 감시·안정화 구현. 다음은 태블릿 실제 프레임 저장→ROI 설정→정답 데이터→가림/끊김/재연결 검증. SPEC-003-WI-01~03은 실제 촬영/공통 계약 AC 미충족으로 implementing 유지. 서버 전송 WI-04는 pending.
- 다른 파트의 작업은 역할 담당과 실제 별도 저장소/미공유 코드 존재 여부를 확인한다.

## 상태 변경 기록

- 2026-10-18 PR #13 지적3건을 b09cf19에서 수정·재검증 후 ba2dc65로 squash merge, WI-02 done. WI-03 서버 단일 큐·브라우저 음성·교신/모의 구간 억제·발생 건별 완료 구현·backend454/frontend36/HTTP47/빌드 검증 후 cd1f895·[PR #14](https://github.com/kkyo1130/Boeing_RADAR/pull/14) reviewing. done10/reviewing1/implementing3/pending21. [WI-03 상세 기록](006-advisory-interface/workitem/wi-03.md).

- 2026-10-18 PR #12 P2 세 건을 f741754에서 수정·frontend18/backend419/HTTP43/공통 계약 검증, 스레드3개 해결 후8c3a796에 squash merge. WI-01 done. WI-02 근거 패널/미디어·사용자 확인 구현, frontend22/backend436/HTTP45/빌드·실제 브라우저 인수 후 커밋f733140·[PR #13](https://github.com/kkyo1130/Boeing_RADAR/pull/13) reviewing. done9/reviewing1/implementing3/pending22. [WI-02 상세 기록](006-advisory-interface/workitem/wi-02.md).

- 2026-10-18 PR #11 P1/P2를d671bf9에서 수정·backend418/HTTP43·공통 계약 통과, 스레드2개 해결 후45afa06으로 squash merge. SPEC-007-WI-01 done. SPEC-006-WI-01 서버 운영 화면·프런트15개/빌드·실제 브라우저 API 인수 후 커밋dc2a840·[PR #12](https://github.com/kkyo1130/Boeing_RADAR/pull/12) reviewing. done8/reviewing1/implementing3/pending23. [WI-01 상세 기록](006-advisory-interface/workitem/wi-01.md).

- 2026-10-18 PR #10 자동 리뷰 완료·지적 없음·스레드0을 확인해 squash merge602a46e. SPEC-005-WI-03 done. SPEC-007-WI-01 발생 건·새 관측 해결·부분 대체·미해결 종료·원자 Trace 구현/검증 후 커밋74a85ae·[PR #11](https://github.com/kkyo1130/Boeing_RADAR/pull/11) reviewing. done7/reviewing1/implementing3/pending24. [WI-01 상세 기록](007-closed-loop/workitem/wi-01.md).

- 2026-10-18 PR #9 문서 P2(상태 API 고정 UNVERIFIED 설명) 수정7066a08 후 squash mergeb3262cf. WI-02 done. WI-03의81개 혼합 조합·API/HTTP 회귀·실행 격리 검증을 추가해 backend393/HTTP37 통과 후 전용 커밋/PR reviewing. done6/reviewing1/implementing3/pending25. [WI-03 MD 상세 기록](005-safe-validation/workitem/wi-03.md).

- 2026-10-18 PR #8 P2(raw ALT의 숨은 HDG 명령) 수정23a902c·backend254/HTTP24 통과 후 squash merge525f98a, WI-01 done. WI-02의3상태·소유권·정확5초/조기 완료/지속 감시·원자 타이머 구현. backend288/HTTP26 검증 후 전용 커밋/PR reviewing. done5/reviewing1/implementing3/pending26. [WI-02 상세 기록](005-safe-validation/workitem/wi-02.md).

- 2026-10-18 [PR #7](https://github.com/kkyo1130/Boeing_RADAR/pull/7)은 head7bd3544에 대한 자동 리뷰 완료·지적 없음·미해결 스레드0을 확인하고 squash merge(`d46c3ac`). 다음 SPEC-005-WI-01 결정론적 구조 검사·수신 보류·원자 Trace·Schema/문형 fixture를 구현하고 커밋7a4a1b8·[PR #8](https://github.com/kkyo1130/Boeing_RADAR/pull/8) 제출. 상태 done4 / reviewing1 / implementing3 / pending27. 구현·검증·리뷰·인수인계는 [WI-01 상세 기록](005-safe-validation/workitem/wi-01.md)을 따른다.

- 2026-10-18 사용자 요청으로 [PR #6](https://github.com/kkyo1130/Boeing_RADAR/pull/6)을 squash merge(`aae3113`)해 WI-02 done. WI-03 HTTP 통합21개·기존 backend174개·계약 Schema6종/fixture21개 검증 후 별도 커밋/PR 제출, reviewing. done3 / reviewing1 / implementing3 / pending28. 다른 WI와 기존 작업 디렉터리의 미커밋 변경은 보존.

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

## SPEC-002-WI-01 PR 제출 · 2026-10-17

공통 v2 DTO·JSON Schema6종·예제21개 검증 및 backend117개 테스트 통과. 계약 상세와 수행 근거는 [WI-01 기록](002-observation-contracts/workitem/wi-01.md)을 따른다. 상태는 PR 검토 중(reviewing)이다. 전체 스펙 문서 구조 변경·다른 WI는 이번 PR에서 갱신하지 않는다. 기존 PR #4에 같은 WI의 다른 계약안이 있어 정합성 검토 후 병합 방향을 결정해야 한다. 실제 v2 API 수신·DB 저장·실장비 연동은 미완료다.

## WI-01 병합·WI-02 검토 · 2026-10-18

PR #5는 사용자의 최신 병합 지시에 따라 기존 지적2건 해결·123개 테스트 통과·충돌 없음 확인 후 squash merge(`5515878`)했다. GitHub 리뷰 상태 COMMENTED를 APPROVED로 보고하지 않는다.

WI-02는 이 dev 기준 별도 브랜치에서 수신/문맥/중복/시간/원자 저장·migration을 구현하고 backend172개 테스트를 통과했다. 실제 모델·실장비·최종 숫자 비교는 후속 범위이며 reviewing으로 PR을 제출한다. WI-03과 다른 WI 상태는 유지한다.

## PR #4 v2 통합 — 2026-10-22

사용자 요청으로 기존 PR #4를 v2 기준으로 정리한다. 별도 v1 화면·수신·판정·사건 엔진은 제거하고 음성/Vision 어댑터, 근거 파일 저장, 종료 리포트, 평가/CI를 v2에 연결한다. 세부 변경·검증·제약은 [통합 작업 기록](../development/pr4-v2-integration.md) 참조. 기존 WI의 실장비 인수 상태를 자동 완료 처리하지 않는다.

## 2026-10-23 사용자 요청 추가 범위

기존35개 WI의 전체 완료/상태와 구분되는 추가 시연 콘솔이다.

| WI | 작업 | 선행 기반 | 상태 |
| --- | --- | --- | --- |
| [SPEC-009-WI-05](009-evaluation-demo/workitem/wi-05.md) | 노트북 장치·ROI·복창·등록 관제를 조작하는 로컬 시연 콘솔 | 기존 v2 운영·근거·음성 우선순위, 로컬 Whisper, Vision OCR | reviewing |

## 2026-11-09 소형 조종사 화면 추가

| WI | 작업 | 담당 | 선행 | 상태 |
| --- | --- | --- | --- | --- |
| [SPEC-006-WI-05](006-advisory-interface/workitem/wi-05.md) | 소형 디바이스 조종사 화면 | Codex (이번 요청 구현) | SPEC-006-WI-01, SPEC-006-WI-02 | reviewing |

기존 WI-02 완료 이력을 유지하고 이번 추가 화면만 독립 PR로 검토한다.

## 2026-11-09 BERT+보완 규칙 STT 연결

SPEC-004-WI-02의 요청 범위 추가 구현을 `origin/dev` `4a6fd74` 기반 `codex/bert-hybrid-stt`에서 reviewing으로 제출한다. BERT CALLSIGN+규칙 ACTION/ALT/HDG를 로컬 Whisper WAV 경로에 연결했다. 실제 모델 포함 backend **532 passed**(skip 없음, deprecation 경고1), 실제 HTTP 음성4사례에서 정상 복창/방위 불일치/무음 보류/호출부호 누락 보류, frontend proxy 연결을 확인했다. 두 정상·불일치 음성은 합성, 사용자 음성은 이전 녹음 재생이며 새 live 마이크·실제 ATC·카메라 E2E는 미실행이다. 공유 기본은 v7 유지, 새 조합은 명시 설정한다. 상세 근거는 [WI-02 기록](004-speech-communication.md#wi-02)과 [실행 안내](../bert-hybrid-stt-integration.md)를 따른다. 다른 WI 상태는 바꾸지 않는다.

제출: [PR #21](https://github.com/kkyo1130/Boeing_RADAR/pull/21), 구현 커밋 `98e6015`. 자체 검토 완료, 외부 리뷰·병합 대기.

2026-11-09 실제 마이크 후속: 신규3회 녹음→Whisper→BERT+규칙→저장·보류 확인. 최종 정상 복창0/3; 약신호, 호출부호 누락, `two/to` 오인식에 따른 hybrid HDG 누락을 기록. reviewing 유지, 세부 원인과 한계는 WI-02/실행 안내 참조. 코드 변경·회귀 재실행 없음.

2026-11-09 숫자 동음어 후속: 명시 숫자 슬롯 후보만 보완. 실제 모델 포함549 passed. 동일 원본 WAV3개 재전사 불변, 마지막 녹음은 구조PASS·복창NORMAL, 앞의 약신호/누락2개는 보류 유지. PR #21 reviewing, 실제 음성 정확도 개선 수치로 일반화하지 않는다.

2026-11-09 PR #21 병합 전 확인: 최초98e6015 자동리뷰 지적없음, 이후e7b1e9e까지 자체 추가검토 지적없음. 원격 Python Ubuntu/macOS 성공, Linux frontend E2E의 기존 `/private/tmp` 캡처 경로3건 실패를 testInfo.outputPath로 수정. 로컬 Node24+Chromium E2E6 passed. 최신 원격 CI를 확인한 뒤 사용자 지시에 따라 squash merge하며 전체 AC 완료와 구분한다.

## ATC 마이크 수음 모드 · 2026-11-10

SPEC-004-WI-02 추가 요청 범위를 `d267d4b` 기반 `codex/atc-microphone-modes`의 구현 커밋 `67852b8`·[PR #22](https://github.com/kkyo1130/Boeing_RADAR/pull/22)를 reviewing으로 제출했다. ATC 수음/Pilot 복창을 분리하고 실제 ATC WAV→STT 경로, 파일 재생→마이크 캡처 UI, 취소·실패 후 과거 지시 재사용 차단을 구현했다. backend560/frontend53/브라우저7/빌드 통과. 실제 UWB-ATCC3개 원음 및 물리 스피커→마이크 각3개는 처리·보류 경로를 확인했으나 지시 채택0/3이며 실제 STT 성능 개선이 남았다. [WI-02 상세 기록](004-speech-communication.md#wi-02)과 [재현 안내](../atc-microphone-modes.md)를 따른다. 다른 WI 상태와 미완료 전체 인수 범위는 유지한다.

## 호출부호 STT 문맥 · 2026-11-10

SPEC-004-WI-02 요청 범위를 `codex/atc-callsign-context`에서 reviewing. 최신 dev d267d4b에서 시작해 ATC 수음 의존 PR #22의 da0f219를 가져왔다. 세션에 등록된 호출부호 발음을 Whisper hotwords로 전달하고 동일 실제 음원으로 전후/목록 밖 음성/호출부호 부재를 비교한다. 외부 교통 목록 연동이나 평가 정답에서 힌트 생성은 제외한다.

완료 근거: 실제23개+합성무음1개 두 조건48회, 실제 모델 ASGI2건, backend571 passed. 등록 데모 호출부호0/3→1/3, 목록 밖3/12 유지; 상세 한계·보류 정책은 [문맥 보고서](../atc-callsign-context.md)와 WI-02를 따른다.

제출: `7a5da03`, [PR #27](https://github.com/kkyo1130/Boeing_RADAR/pull/27). PR #22에 의존하는 별도 PR이며 외부 리뷰·병합 대기.

## 고도·방위 음성 숫자 규칙 보완 · 2026-11-10

SPEC-004-WI-02의 요청 범위를 `codex/atc-numeric-rules`에서 reviewing. 최신 dev d267d4b에서 시작해 앞 단계 PR #27의203e5e0을 의존성으로 가져왔다. FL2/3자리·완전한 백 단위·음성 heading360→0을 지원하며 wire/OCR 범위는 유지한다. heading 직후 단일 머뭇거림은 후보 추출만 허용하고 구조 보류한다. 기존88개와 문맥 시험24개의 고정 전사를 사용해 규칙 변경만 대조한다.

완료 근거: 고정224조건/실제 BERT222회, 고도11/15→13/15·방위7/13→10/13, 이전 정답 필드 회귀0. backend623 passed·공통 계약 검사 PASS. 숫자 후보와 자동 채택의 차이·재사용 자료 한계는 [숫자 규칙 보고서](../atc-numeric-rules.md) 및 WI-02를 따른다.

제출: `dfb25c7`, [PR #28](https://github.com/kkyo1130/Boeing_RADAR/pull/28). PR #27 의존, 외부 리뷰·병합 대기.

## 2026-11-11 사용자 요청: 조종석 + OCR v3 로컬 실행

`feat/vision-ai`에서 기존 GLB/Three.js와 별도 웹캠 ROI·v3 추론 연결. 상태: verifying (실제 촬영 OCR 정확도 미검증, 미커밋). 기존 SPEC-003/006 WI의 전체 인수 상태는 유지한다. 변경·검증·실행·제약 원본은 [실행 기록](../development/vision-webcam-v3.md).

2026-11-11 후속 요청: 웹캠 수동 ROI 선택을 제거하고 전체 프레임의 HDG·ALT 자동 탐지와 연속 v3 OCR을 연결했다. verifying 유지. 단위6·frontend56·합성 카메라 자동 탐지 smoke 통과, 실제 촬영 인수는 미실행. 변경·한계는 [실행 기록](../development/vision-webcam-v3.md#2026-11-11-자동-숫자-창-탐지-후속)에 기록했다.

2026-11-11 웹캠 수집 후속: 학습용 고정 캡처·HDG/ALT 사람 정답 확인·로컬 저장 추가. verifying 유지. Vision 관련12·frontend56·수집 UI smoke·빌드 통과. 실제 사용자 정답 샘플 수집과 재학습/평가는 미실행. [실행/검증 기록](../development/vision-webcam-v3.md#웹캠-학습용-캡처와-사람-확인-정답-수집).

## 2026-11-12 카메라 정답과 모의 3D 화면 동기화

사용자 요청 추가 범위: verifying. 대상 display ACK·렌더 프레임·만료·촬영 차단·8조합 120쌍 수집을 구현. 실물 태블릿/카메라 인수는 미실행. [구현·검증·인수인계](../../vision/docs/camera-display-sync.md). 기존 WI 전체 완료 상태는 유지한다.

## 2026-11-12 CNN v6 카메라 학습 파이프라인

사용자 요청 추가 범위: verifying. 기존 프리셋·ACK를 보존하고 학습160/테스트40 수집, 기존120+신규160+합성 다중 병합, v5 초기 가중치·별도 v6 저장, 독립 동일 테스트 비교를 구현. 실제 신규 촬영/공식 v6 학습·성능 개선 확인은 미실행. [구현·검증·리뷰·인수인계](../../vision/docs/cnn-v6-pipeline.md). 기존 WI의 실물 인수 상태는 유지한다.

## 2026-11-12 실제 카메라 YOLO MCP 개선

사용자 요청 추가 범위: verifying. 합성 baseline 분석, 세션별 수집·수동 전체 MCP 라벨, 합성/실제 혼합 학습과 동일 실물 테스트 지표/IoU/오버레이 비교, OCR 전달 게이트 구현. 실제 촬영·공식 학습·실물 개선 검증은 미실행. [구현·검증·리뷰·인수인계](../../vision/docs/yolo-real-camera.md). CNN/ACK·기존 WI의 인수 상태는 유지한다.

## 2026-11-12 YOLO 자동 수집·전수 검토

사용자 요청 추가 범위: verifying. 기존 수동 수집을 보존하고 2초 자동 촬영·안정 후보/검토 분리·근접 중복 제외·전체 인간 검토/박스 수정·승인 이력과 학습 파일 대조를 구현. 실제 Mac 카메라/MPS/GUI 인수는 미실행. [구현·검증·리뷰·실행](../../vision/docs/yolo-auto-capture.md). 기존 CNN/ACK/3D 작업 상태는 유지한다.

## 2026-11-12 실제40장 YOLO 게이트 진단

사용자 요청 추가 범위: verifying. IoU 분모/게이트 전체 원인/라벨 teacher bias/validator와 predict의 전처리 차이를 분리하고 같은40장 MPS 재평가·80장 오버레이·CSV/HTML 생성. CNN/React/임계값·원본은 유지. [분석·검증·실행·제한](../../vision/docs/yolo-gate-diagnosis.md). 독립 블라인드 라벨과 실시간 인수는 미실행.

## 2026-11-12 YOLO 블라인드 재라벨링 v2

사용자 요청 추가 범위: verifying. 원본190장 보존, 학습/검증150장 블라인드 수동 라벨·별도 이력, 기존test40 hash/session 은퇴, 신규 독립 테스트 수집·최종 비교 정책·고정3프레임 영상 검증 도구 구현. 회귀107 passed. 실제 GUI 라벨링/신규 촬영/공식 학습·최종 평가·실시간 인수는 미실행. [구현·검증·실행·인수인계](../../vision/docs/yolo-blind-v2.md). 미커밋, 기존 CNN/React 작업 상태 유지.

2026-11-12 CNN v6 수집 재개: verifying 유지. blind_v2 YOLO 기반 단계 도우미와 실패 원본 저장 추가. 실제300프레임 진단·실패30장 저장, 회귀107 통과. 중복헤더 기존배치 보존·새 _02 배치 시작 확인. 신규160/40 완성·학습·비교는 미실행. [후속 실행 기록](../../vision/docs/cnn-v6-pipeline.md#2026-11-12-실제-카메라-수집-재개-준비).

CNN v6 수집 CSV 재개 버그 후속: verifying 유지. 중복헤더 생성 수정·원본CSV 백업 후 헤더1행 제거, 실제 신규160쌍/기존120쌍 검증·누수검사 PASS, 회귀68 통과. 독립test40 미수집으로 학습/비교는 대기. [오류 수정 기록](../../vision/docs/cnn-v6-pipeline.md#csv-재개-오류-수정-및-실제160쌍-검증).

CNN v6 추가컬럼 병합 후속: 실제 합성 crop좌표 보존 수정·실패preflight 보존·실제 prepare-only 성공. 신규test40 검증 완료, 회귀68 통과. 공식학습/비교 미실행, verifying 유지. 상세는 CNN v6 실행 기록 참조.

## v5 카메라 OCR crop 감사·개선 후보

verifying. 실제 테스트80crop 전수/학습32대표crop 대조·문자별혼동 보고서 생성. 별도 카메라 개발검증/초기v5 baseline 보존 선택 구현, 실제 MPS12epoch 후보학습 완료. 개발HDG40/40·ALT35/40(ALT v5tensor동일), 독립최종 개선검증 아님. 회귀109 통과, 새 final03 수집/비교 연결. 기본모델·원본·안전기준 유지. [구현·검증·인수인계](../../vision/docs/ocr-v5-improvement.md).

## 2026-11-12 실제 웹캠 문자열80% 목표 개선

verifying(광범위 실물 인수 대기). 부분 숫자crop·거리별 밝은 테두리 유입 확인/추출기 개선, 위치공유 글자CNN v2 실제MPS20epoch 학습, 새 카메라20조합400프레임 고정평가 완료. HDG/ALT 각각360/400=90%(추출360중100%), 추가OCR3프레임 재생320/400=80%. 단일 최종촬영 조건·상관프레임 제한, 보편정확도 아님. 실패한04–07 보존·06은 명시적 개발학습전환,08은모델고정후촬영. 회귀116통과, 실시간 선택형 창 실행, 기본모델/원본/React/안전기준 유지. [구현·실험·검증·인수인계](../../vision/docs/character-ocr-camera.md). 미커밋.

2026-11-12 숫자 표시창 세로 비율 조정: 사용자 요청으로 Cockpit3D.jsx 숫자 텍스트 높이30%·검은 창/테두리 높이20% 확대, 중심y .58→.5로 배치. 가로폭/설정값/ACK/모델 보존. frontend build 통과(기존 번들 크기 경고), 실물 OCR 정확도 재평가는 미실행; 기존90% 결과를 새 표시 비율 정확도로 재사용하지 않는다. 미커밋.

## 2026-11-12 표시창·HDG/ALT 선명도와 Vision 회귀

verifying(범용 촬영 인수는 대기). MCP세로압축 완화·숫자높이 직전대비약44%/검은창51% 확대,4배텍스처·매트배경·큰 선명라벨 구현. 저성능 확대/좁은글자 후보 철회. 고정MCP정면 동일15조합300프레임 검증에서 최종HDG/ALT raw문자열각90%, 추출270중100%, 라벨전후accepted/coverage/OCR3지표동일; 최소90% 포함14검사PASS. ALT1건낮은점수차단유지(accepted-correct89.67%), OCR3재생HDG80/ALT79%. 테스트시점잠금원복,모델·게이트·ACK·원본 유지. ENOSPC로 미완료한당일임시JPEG만정리, 기존데이터삭제없음. frontend58/빌드PASS. [구현·카메라근거·제약](../../vision/docs/readout-style-review.md). 미커밋.

표시창 후속 최종 검증: Vision120 passed(4.94s), frontend58 passed, 빌드통과. 선택형새CNN실시간창재실행. 최종소스/정면고정회귀문서와시각비교저장, 시점시험잠금해제.

2026-11-12 GitHub 제출 준비: feat/vision-ai의 사용자 요청 Vision 변경을 커밋·푸시한다. AI가중치/촬영원본/로컬상세보고서/백업은 제외하며 경로를 정리한 실측 요약은 vision/evaluation/camera-20261112.json에 포함. 광범위 실물 인수·미검증 조건 상태는 그대로 유지한다.

GitHub 제출 전 최종검증: Vision120 passed(5.08s), frontend58 passed, frontend build PASS(1.25s; 기존chunk경고). 스테이징56파일의 대용량원본/가중치/백업/개인절대경로 점검통과. 기존단계의 verifying는 실물범용인수상태로유지.
