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
| [SPEC-004-WI-02](004-speech-communication.md#wi-02) | ATC/Pilot STT와 문맥 구조화 | P0 | 노남경 | SPEC-004-WI-01, SPEC-002-WI-02 | pending |
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

| [SPEC-009-WI-06](009-evaluation-demo/workitem/wi-06.md) | GLB 전체 조종석 메시·MCP 수동 조작·시점 전환 | 기존 MCP UI | reviewing |

## 2026-11-12 Flight Safety Report·PDF

사용자 첨부 요청 추가 범위 [SPEC-008-WI-05](008-safety-trace-report/workitem/wi-05.md): verifying. 기존 입력/Trace/Incident/고정 리포트를 확장해 5개 섹션, 사건 중복 방지·미해결 분리, 브라우저 접근 권한, 규칙/선택적 AI 요약, 한글 PDF와 실제 다운로드를 구현했다. 기존 WI의 실제 장치 인수를 자동 완료로 바꾸지 않는다. 변경·검증·리뷰·실행·제한은 해당 WI 문서에 기록한다.

2026-11-12 리포트 브랜드 제거 후속: PDF머리글/제목/작성자, 리포트UI상단, 서버·브라우저다운로드명 정리. 새 파일명 Flight_Safety_Report_<UTC 종료일>.pdf. 관련backend17/frontend49/다운로드E2E1 및빌드통과, fixture PDF4쪽재생성·렌더검토. 저장된데이터·폴더/저장소URL·기종출처이름은유지. [수정위치·검증기록](008-safety-trace-report/workitem/wi-05.md#2026-11-12-리포트-브랜드-문구-제거-후속). 기존WI검증상태유지, 미커밋.

## 2026-11-12 ZIP AI 연결

[SPEC-009-WI-07](009-evaluation-demo/workitem/wi-07.md): verifying. 사용자 요청으로 ZIP Whisper·BERT·OCR을 기존 프로젝트에 연결. 모델은 ZIP 경로 참조, 별도 로컬 DB/포트 사용. 13개 테스트 통과; 실제 마이크·카메라 검증과 PR 제출은 미실행.

2026-11-12 WI-07 후속 verifying: 사용자 요청으로 ZIP 음성·운영·Pilot 기능을 병합하고 기존 Report/PDF와 Vision 소스·모델 참조·LAB 화면을 보존했다. backend680/HTTP50/Vision API57/frontend69 및 빌드 통과. 실장비·브라우저 조작·전용 PR은 미실행. [상세 기록](009-evaluation-demo/workitem/wi-07.md#2026-11-12-음성운영-zip-통합-및-vision리포트-보존-후속).

## 2026-11-12 사진 증강·추가 학습

[SPEC-003-WI-06](003-cockpit-vision/workitem/wi-06.md): verifying. 사용자 승인으로 원본과 해시 일치하는 학습용 복사본 약1GB 정리, 사진 숫자/각도 코드 합성600쌍 생성, 별도 OCR 후보 학습. 기존 모델/원본/평가 기록 보존. 실제 실행 모델 교체와 독립 실카메라 인수는 포함하지 않는다.

2026-11-12 WI-06 결과: 사진 합성600쌍 및 원본 train 혼합으로 HDG/ALT16epochs 후보 학습 종료. 소비된 개발40장씩에서 HDG20/40·ALT24/40으로 부족해 실행 모델 교체하지 않음. Vision 회귀62개 통과. [상세 결과](003-cockpit-vision/workitem/wi-06.md#학습-결과). 독립 실카메라 평가와 PR 미실행, verifying 유지.

2026-11-12 WI-06 빛번짐 후속 verifying: 빛번짐 합성300쌍, render ACK 기반 실제20조합60프레임 train 촬영 완료·270/03000 복원. 단계별 CNN 단독 진단 및 회귀64개 통과. 두 번째 실제 각도/거리 조건 변경 확인 대기이며 새 후보 학습·새 독립 최종 평가는 미실행. [진행 기록](003-cockpit-vision/workitem/wi-06.md#빛번짐실촬영단계-분리-평가-후속-진행-중).

2026-11-12 WI-06 후속 verifying: train실촬영122장·개발24장·동결 후 새최종36장 수집, 빛번짐300쌍 합성 및character 후보 학습. 최종 동일ROI에서 새결합 HDG36정답/0오답/0보류, ALT35정답/0오답/1보류로 로컬 적용. 기존결합 ALT오답1건을 보류로 전환. 상관된12설정그룹의 제한된 측정이며 독립 반복/브라우저 안정화 인수는 남음. Vision71개·무정보 live API 검증 통과. [상세](003-cockpit-vision/workitem/wi-06.md#실제-각도-추가개발-분리동결-최종-평가-결과).

2026-11-12 SPEC-003-WI-06 reviewing: [Draft PR #35](https://github.com/kkyo1130/Boeing_RADAR/pull/35), 전용브랜치 codex/glare-capture-training-20261112→feat/vision-ai. 구현69732bd 격리worktree에서도Vision71개통과. 실제새36장범위에서새결합 HDG36정답·ALT35정답/1보류/출력오답0, 로컬적용·원본보존. 기존사용자브랜치/미커밋변경보존. 외부리뷰/병합·독립반복인수미실행.

## 2026-11-12 파일 음성 직접 STT

[SPEC-004-WI-05](004-speech-communication/workitem/wi-05.md): verifying. 사용자 요청으로 관제/조종사 복창 각각 파일 직접 STT 버튼과 사용법 구현. frontend75/backend684·실제Whisper/BERT 합성파일 임시DB 검증 통과, 브라우저 파일 선택은 제어 연결 문제로 미실행. 기존 마이크·카메라·리포트·비행DB 보존.
