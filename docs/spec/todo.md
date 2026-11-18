# RADAR 전체 작업 목록

기준일: 2026-10-18. PR #14 리뷰2건 수정 후 squash merge한 dev(`75e74ac`) 기준이다. SPEC-006-WI-03 done, WI-04는 합성 통합 검증을 마치고 실장비 선행 결과를 기다리는 verifying이다.

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
| [SPEC-006-WI-03](006-advisory-interface.md#wi-03) | 보조 음성·억제 정책과 선택 경고 단계 | P0/P1 | 노남경 | SPEC-006-WI-02 | done |
| [SPEC-006-WI-04](006-advisory-interface.md#wi-04) | 알림·근거 화면 전체 검증 | P0 | 노남경 | SPEC-006-WI-03, SPEC-003-WI-05, SPEC-004-WI-04 | verifying |
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

[구현 현황](../IMPLEMENTATION_STATUS.md)에 SPEC별 기존 기반과 남은 범위를 정리했다. 비교·재검증·기본 Trace 등 Mock 서버 기반이 이미 있지만 자문 반영 확장 WI의 전체 완료 조건은 미충족이라 pending을 유지한다. 11/35 done을 제품 완성률로 해석하지 않는다.

## 다음 작업

- UI: WI-04 합성 HTTP/React 통합 검증을 완료했다. SPEC-003-WI-05·SPEC-004-WI-04 실제 입력 증거 연결 후 최종 인수한다. SPEC-007-WI-02 실제 수정 입력 연결은 SPEC-003-WI-04·SPEC-004-WI-04가 더 필요하다.
- 세현님: 태블릿용 MCP 화면과 Vision 영상/웹캠·상태 감시·안정화 구현. 다음은 태블릿 실제 프레임 저장→ROI 설정→정답 데이터→가림/끊김/재연결 검증. SPEC-003-WI-01~03은 실제 촬영/공통 계약 AC 미충족으로 implementing 유지. 서버 전송 WI-04는 pending.
- 다른 파트의 작업은 역할 담당과 실제 별도 저장소/미공유 코드 존재 여부를 확인한다.

## 상태 변경 기록

- 2026-10-18 PR #14 리뷰2건 수정850dd17·backend455/frontend39/HTTP47/빌드·계약 재검증 후75e74ac로 squash merge, WI-03 done. WI-04 HTTP50/실제 서버 응답→React5/브라우저 카메라 장애·음성·새 영상 복구 인수. 실장비 선행 결과 미완료로 verifying·커밋7e24960·[초안 PR #15](https://github.com/kkyo1130/Boeing_RADAR/pull/15) 제출. done11/verifying1/implementing3/pending20. [WI-04 상세 기록](006-advisory-interface/workitem/wi-04.md).

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

## 2026-11-16 사용자 첨부 Operation·Vision·기록 개선

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-006-WI-05](006-advisory-interface/workitem/wi-05.md) | Operation 기본 문구·ID·사용법 정리 | reviewing |
| [SPEC-003-WI-07](003-cockpit-vision/workitem/wi-07.md) | 자동·수동 ROI 공통 OCR·관측 경로 | reviewing |
| [SPEC-003-WI-08](003-cockpit-vision/workitem/wi-08.md) | 새프레임3회·인식일정·상세시간진단 | reviewing |
| [SPEC-008-WI-06](008-safety-trace-report/workitem/wi-06.md) | polling독립기록·확정리포트·전체인쇄 | reviewing |

기존35개WI 및 실장비인수 상태는 유지한다. 각WI의 구현·검증·자체리뷰·인수인계는 링크한기록참조. 실장비지연비교/실제프린터/외부리뷰는미실행.

2026-11-16 사용자 명시 승인으로 새 기준·작업 브랜치 푸시와 Draft PR 제출을 완료했다. 실장비 인수·외부 리뷰·병합은 미실행이다.

PR 연결: [UI #36](https://github.com/kkyo1130/Boeing_RADAR/pull/36) → [ROI #37](https://github.com/kkyo1130/Boeing_RADAR/pull/37) → [인식 일정 #38](https://github.com/kkyo1130/Boeing_RADAR/pull/38) → [리포트 #39](https://github.com/kkyo1130/Boeing_RADAR/pull/39).

## 2026-11-16 사진 기준 Cockpit 비율 조정

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-009-WI-08](009-evaluation-demo/workitem/wi-08.md) | HDG·ALT/MCP 비율 정리와 동일 실행 모델 paired 비교 | verifying |

화면 캡처 기반 새24화면/48필드 비교: 이전 정답47·보류1·오답0, 변경 정답48·보류0·오답0. 실제 카메라 재촬영/물리 태블릿 인수와 외부 리뷰는 미실행이다.

## 2026-11-16 이동 중 카메라 추적·재탐색

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-003-WI-09](003-cockpit-vision/workitem/wi-09.md) | 매 프레임 자동 영역 갱신·동적 박스·탭 전환/놓침 후 연속 재탐색 | verifying |

backend692/skip7, frontend79·빌드, 모의 카메라 브라우저4, 로컬 렌더 이미지+native OCR+임시 DB API1 검증. 실제 웹캠 이동·장시간 배경 탭 인수와 외부 리뷰·원격 게시는 미실행이다.

## 2026-11-16 리포트 중복 표시 제거

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-008-WI-07](008-safety-trace-report/workitem/wi-07.md) | 반복 관측·사건 갱신·검증표 집계와 화면/PDF/인쇄 공통 표시 | verifying |

실제 최신 리포트 원본817개·오류1개를 보존하며 PDF102→11쪽. 원본 고정 JSON 불변 확인, frontend81·빌드·브라우저4 통과. 원격 게시·외부 리뷰·실제 프린터 출력은 미실행.

## 2026-11-17 YOLO + CNN 복구와 실제 웹캠 검증

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-003-WI-10](003-cockpit-vision/workitem/wi-10.md) | YOLO 자동 영역·추적 + 공통 CNN, Apple Vision 대체 제거, 실제 촬영 검증 | verifying |

## 2026-11-17 오류 사건 중심 보고서

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-008-WI-08](008-safety-trace-report/workitem/wi-08.md) | 사건당4단계 기본 타임라인·전체기록 접기·PDF/인쇄 요약 | reviewing |

backend701/skip7, frontend82·빌드, 브라우저4 통과. 실제 고정4154이벤트/2사건은8단계/PDF2쪽, 원본 JSON 불변. 외부 리뷰·원격 게시·실제 프린터 미실행.

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-008-WI-09](008-safety-trace-report/workitem/wi-09.md) | AI Safety Summary 화면/PDF 문단·줄간격 개선 | reviewing |

## 2026-11-17 Operation 입력 UI 정리

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-006-WI-06](006-advisory-interface/workitem/wi-06.md) | 중복 음성 방식·예비 시나리오·모의 시험·사용법 제거, Cockpit 링크 정리 | reviewing |

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-006-WI-07](006-advisory-interface/workitem/wi-07.md) | 음성·장치 설정 하단 독립 결과 섹션과 복명복창/Cockpit 2열 배치 | reviewing |

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-006-WI-08](006-advisory-interface/workitem/wi-08.md) | RADAR AI Flight Guard 브랜드·파랑/하늘색 화면 테마 | reviewing |

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-006-WI-09](006-advisory-interface/workitem/wi-09.md) | 상단 라이트/다크 전환·선택 저장·어두운 배경/패널 | reviewing |


2026-11-17 사용자 요청으로 후속 작업별 Draft PR #40–#49 게시 완료. [게시 기록·선행 관계](publication-20261117.md). 실장비 인수가 남은 WI의 verifying 상태는 유지한다.

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-006-WI-10](006-advisory-interface/workitem/wi-10.md) | 현재 브랜드·Cockpit 문구/누락 검증 기록 게시와 checkout 정리 | reviewing |

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-006-WI-11](006-advisory-interface/workitem/wi-11.md) | 사용자 B&G 상단 로고·favicon·앱 아이콘 연결 | reviewing |
## 2026-11-09 소형 조종사 화면 추가

| WI | 작업 | 담당 | 선행 | 상태 |
| --- | --- | --- | --- | --- |
| [SPEC-006-WI-05](006-advisory-interface/workitem/wi-05.md) | 소형 디바이스 조종사 화면 | Codex (이번 요청 구현) | SPEC-006-WI-01, SPEC-006-WI-02 | reviewing |

기존 WI-02 완료 이력을 유지하고 이번 추가 화면만 독립 PR로 검토한다.

2026-11-11 SPEC-006-WI-05 후속: 사용자 요청으로 `/pilot`의 버튼·판정·보류·장치 안내를 영어로 표시했다. `codex/pilot-english`, reviewing. frontend 단위60개·소형 화면 E2E4개·빌드 통과. 상세 범위와 근거는 WI-05 기록을 따른다.

2026-11-11 실제 발화 시험 후속: `codex/pilot-readback-result`, reviewing. 복창 성공을 Pilot에 따로 표시하고 카메라 입력 대기와 구분했다. 단위62개·Pilot E2E5개·빌드 통과, 신규 실제 관제/복창 결과의 Chrome 표시 확인. ATC 최초2회 호출부호 실패와 카메라 미검증은 WI-05에 구분해 기록했다.

## 2026-11-09 BERT+보완 규칙 STT 연결

SPEC-004-WI-02의 요청 범위 추가 구현을 `origin/dev` `4a6fd74` 기반 `codex/bert-hybrid-stt`에서 reviewing으로 제출한다. BERT CALLSIGN+규칙 ACTION/ALT/HDG를 로컬 Whisper WAV 경로에 연결했다. 실제 모델 포함 backend **532 passed**(skip 없음, deprecation 경고1), 실제 HTTP 음성4사례에서 정상 복창/방위 불일치/무음 보류/호출부호 누락 보류, frontend proxy 연결을 확인했다. 두 정상·불일치 음성은 합성, 사용자 음성은 이전 녹음 재생이며 새 live 마이크·실제 ATC·카메라 E2E는 미실행이다. 공유 기본은 v7 유지, 새 조합은 명시 설정한다. 상세 근거는 [WI-02 기록](004-speech-communication.md#wi-02)과 [실행 안내](../bert-hybrid-stt-integration.md)를 따른다. 다른 WI 상태는 바꾸지 않는다.

제출: [PR #21](https://github.com/kkyo1130/Boeing_RADAR/pull/21), 구현 커밋 `98e6015`. 자체 검토 완료, 외부 리뷰·병합 대기.

2026-11-09 실제 마이크 후속: 신규3회 녹음→Whisper→BERT+규칙→저장·보류 확인. 최종 정상 복창0/3; 약신호, 호출부호 누락, `two/to` 오인식에 따른 hybrid HDG 누락을 기록. reviewing 유지, 세부 원인과 한계는 WI-02/실행 안내 참조. 코드 변경·회귀 재실행 없음.

2026-11-09 숫자 동음어 후속: 명시 숫자 슬롯 후보만 보완. 실제 모델 포함549 passed. 동일 원본 WAV3개 재전사 불변, 마지막 녹음은 구조PASS·복창NORMAL, 앞의 약신호/누락2개는 보류 유지. PR #21 reviewing, 실제 음성 정확도 개선 수치로 일반화하지 않는다.

2026-11-09 PR #21 병합 전 확인: 최초98e6015 자동리뷰 지적없음, 이후e7b1e9e까지 자체 추가검토 지적없음. 원격 Python Ubuntu/macOS 성공, Linux frontend E2E의 기존 `/private/tmp` 캡처 경로3건 실패를 testInfo.outputPath로 수정. 로컬 Node24+Chromium E2E6 passed. 최신 원격 CI를 확인한 뒤 사용자 지시에 따라 squash merge하며 전체 AC 완료와 구분한다.

## 관제 전사 후단 추출 평가 · 2026-11-10

SPEC-004-WI-02 reviewing 유지. `codex/atc-slot-evaluation`에서 실제 UWB88개 정답/관제용 Whisper 전사에 기존 BERT+규칙을 적용했다. 추가 실제 음원28개 ASR·두 조건176회 추출·전용6개 테스트와 입력/점수 감사를 완료했다. 방위13개는 이전 평가 원본 그룹과 겹치는 진단임을 분리한다. 제품 코드 변경·전체 WI 완료·병합은 하지 않는다. 상세 결과와 미실행 범위는 [WI-02 기록](004-speech-communication.md#wi-02), [평가 보고서](../atc-slot-evaluation.md)를 따른다.

제출: 평가 커밋 `1b879fb`, [PR #26](https://github.com/kkyo1130/Boeing_RADAR/pull/26). 자체 검토 완료, 외부 리뷰 대기.

2026-11-10 새 관제 녹음 비교: [PR #25](https://github.com/kkyo1130/Boeing_RADAR/pull/25), 결과 `92fa330`. `codex/atc-unseen-whisper`에서 기존 사용 기록과 원본 그룹이 겹치지 않는 UWB test 관제사60구간의 일반/관제용 Whisper 비교를 reviewing. 기본120회+추가진단28회 완료, 전용6 tests·컴파일·결과 감사 통과. 운영 모델은 유지한다. SPEC-004-WI-02의 추가 실험 범위이며 다른 WI는 변경하지 않는다. 최종 근거는 [WI-02](004-speech-communication.md#wi-02)에 기록한다.

2026-11-10 관제 특화 STT 비교: [PR #24](https://github.com/kkyo1130/Boeing_RADAR/pull/24), 코드·실측 `dfdd8ac`, `codex/atc-specialist-comparison`, 기준 dev `d267d4b`. 동일 실제 발화3개×원음/기존 마이크 녹음에서 특화 모델3종·Whisper 안내문2조건,24회 실측. 전용 테스트2개·컴파일·결과 해시/채점 감사 통과. 운영 모델은 유지하며 SPEC-004-WI-02 reviewing. 결과·학습 중복 위험·PR 인수인계는 [WI-02](004-speech-communication.md#wi-02)와 [보고서](../atc-specialist-comparison.md)에 기록한다. 다른 WI 상태는 변경하지 않는다.

## 동일 실제 관제 음원 STT 비교 · 2026-11-10

SPEC-004-WI-02의 모델 선택 추가 실험을 `codex/atc-stt-comparison`·커밋 `fe2cf3e`·[PR #23](https://github.com/kkyo1130/Boeing_RADAR/pull/23)에서 reviewing으로 제출했다. Whisper4종×원음/기존 마이크 녹음×3발화×안내문2조건의 실제 로컬48회 처리 완료, 올바른 채택0·잘못된 채택0이다. 정답 텍스트의 별도 추출 진단3/3 PASS, 채점 테스트5개 통과. 운영 모델은 유지했다. [상세 결과/재현](../atc-stt-comparison.md), [WI-02 기록](004-speech-communication.md#wi-02). 새 제품 기능·전체 독립 성능평가 완료를 의미하지 않으며 다른 WI 상태를 변경하지 않는다.

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

2026-11-10 SPEC-004-WI-02 후속: `codex/atc-live-demo`에서 사람 관제사 직접 발화 모드/역할 근거/실행기 추가. backend627·HTTP47·frontend54·브라우저2·계약22 검증 통과, 실제 모델의 기존 마이크 파일 재생 검증 통과. 새 2인 실시간 녹음은 미실행. [PR #29](https://github.com/kkyo1130/Boeing_RADAR/pull/29), 구현 `3ece4fd`. 선행 PR #28에 의존하며 reviewing 유지. 상세 근거는 SPEC-004-WI-02 수행 기록을 따른다.


2026-11-11 SPEC-004-WI-02 뒤쪽 호출부호 수정: `codex/readback-callsign-suffix`에서 PILOT 경계 호출부호·복창 문형·동작 비교 및 실제 DELTA 원음 재시험을 완료하고 reviewing. 후보 DELTA123/3000ft/270° 추출, 동작 생략/카메라 부재 보류를 유지한다. 전체 backend665/별도 최종42·계약22·빌드 검증. [상세 근거](../readback-callsign-suffix.md), 다른 WI 상태는 변경하지 않는다.

제출 커밋 `7416738`, [PR #34](https://github.com/kkyo1130/Boeing_RADAR/pull/34). 로컬 데모 적용 완료, 외부 리뷰·병합 대기.

## 2026-11-18 열린 PR의 dev 통합

사용자의 전체 반영 요청으로 #36–#51 및 #15를 `codex/dev-pr-integration-20261118`에서 통합 검증했다. Backend/HTTP754(7 skipped)·Vision80·frontend83·HTTP→React5·브라우저14·계약6/22·빌드 통과. 충돌 해결, 음성/터치 보호와 시나리오 잔여 UI 수정 및 CI 의존성 보완은 [통합 기록](../development/pr-stack-integration-20261118.md)에 있다. 코드 병합과 실장비 전체 인수 완료는 구분하며 기존 미완료 AC 상태를 유지한다. 원격 CI/최종 병합 여부는 통합 PR을 따른다.

## 2026-11-18 PDF 요약 + 지시 로그

| WI | 범위 | 상태 |
| --- | --- | --- |
| [SPEC-008-WI-10](008-safety-trace-report/workitem/wi-10.md) | 브랜드 없는 요약 1쪽과 전체 지시별 ALT/HDG 로그 PDF | reviewing |
