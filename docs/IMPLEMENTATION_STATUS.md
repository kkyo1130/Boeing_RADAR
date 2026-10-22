# 2026-10-22 PR #4 통합

v2 화면·API·판정으로 통합했다. 최신 변경/검증은 [통합 기록](development/pr4-v2-integration.md), 실행은 [운영 안내](development/operations.md)를 따른다. 아래는 각 시점의 과거 검증 기록이다.

# RADAR 구현 현황

확인일: 2026-10-10. 현재 dev는 `9d1d561`이며 MCP 정지 이미지 PoC와 공유 문서가 병합됐다. 이번 태블릿 화면·Vision 스트림 작업은 `codex/tablet-mcp-stream`에 포함한 변경이다. 아래 backend 결과는 초기 기준선 검증이며 최신 Vision 검증은 문서 끝의 태블릿 작업 기록을 따른다.

## 구현된 흐름

JSON Mock Observation → Flight/Clearance 관리 → ATC와 Readback 비교 → Cockpit 비교 → 오류 단계 → 수정값 API 입력 → RESOLVED → SQLite Safety Trace 조회.

| 기능 | 현재 구현과 한계 | 코드 근거 |
| --- | --- | --- |
| 비행 시작·조회·종료 | 구현. 종료 후 변경·중복 종료 거부 | `backend/app/services/flight_service.py`, `backend/app/api/flights.py` |
| 지시 생성·목록·상세 | 구현. clearance_id로 입력 연결 | `backend/app/services/clearance_service.py`, `backend/app/api/clearances.py` |
| Observation 수신·검증 | 구현. ALT·HDG·confidence 필수; UTC 시각, 범위/타입 검사 | `backend/app/schemas/observation.py` |
| Readback/Setting 오류 구분 | 구현. ALT·HDG 정확 일치, Readback 우선 | `backend/app/services/validation_service.py` |
| 수정 재검증 | Mock API로 구현. 실제 새 프레임·수정 음성의 freshness는 검사하지 않음 | `backend/app/services/clearance_service.py` |
| Safety Trace 저장·조회 | 기본 이벤트·관측 스냅샷·수정 전후 값 보존. 근거 파일·보류·health·억제·사용자 확인은 없음 | `backend/app/services/safety_trace_service.py`, `backend/app/models/safety_event.py` |
| 경고 | ALERTED 이벤트 저장만 있음. 화면·음성·경고 단계·억제 정책 없음 | `backend/app/core/enums.py`, `backend/app/services/clearance_service.py` |
| Swagger | 13개 메서드별 API 엔드포인트 | `backend/app/main.py` 및 API 라우터 |

`RECOGNIZED`라는 이벤트명은 실제 AI 인식 성공을 의미하지 않는다. 현재 API에 전달한 JSON 값을 기록하는 이름이다. Readback 수정의 RESOLVED는 복명복창 오류 해소이며 Cockpit이 없으면 전체 3단계 검증 완료는 아니다.

## 기능 스펙 기준 진행 상황

| 스펙 | 이미 있는 기반 | 목표 기준 남은 일 |
| --- | --- | --- |
| SPEC-001 개발 환경 | monorepo 구조·backend 이동·기존 테스트 완료 | 파트별 실행/버전·설정, 반복 가능한 자동 검증 기반 |
| SPEC-002 관측 계약 | 기본 DTO·지시 ID 연결·입력 순서/중복 거부 | 부분 지시·null·health·품질·근거·버전·stale/역순 정책 |
| SPEC-003 Vision | 정지 이미지/영상/카메라 입력·ROI 도구·숫자/단위 검사·근거·상태 감시·연속 안정화 | 태블릿 실촬영·품질 평가·공통 계약·서버 연동·실장비 인수 |
| SPEC-004 통신/음성 | 디렉터리만 있음 | 수신·전처리·분리·STT·문맥 구조화·품질 감시 전부 |
| SPEC-005 판정 | 정확 비교·오류 단계·필수 입력 범위 검증 | UNVERIFIED, 추출 후 규칙 교차검사, 품질/freshness 고려 |
| SPEC-006 화면/알림 | backend Flight API와 ALERTED 기록; 별도 frontend 태블릿 MCP 수동 화면 | 서버 운영 화면·근거 패널·실시간 표시·음성/억제·경고 단계 |
| SPEC-007 Closed-loop | Mock 수정 API·REVERIFYING/RESOLVED 기록 | Incident 연결·관측 freshness·실입력 수정 재인식·전체 시연 |
| SPEC-008 Trace/Report | 기본 Trace DB·조회 API | 확장 이력·집계·리포트 화면·해결 시간/경고 이력 |
| SPEC-009 평가/시연 | 기존 Mock backend 테스트 | 라벨 영상/음성·거짓 정상/보류/지연 평가·교육 모드·실장비 E2E |
| SPEC-010 선택 확장 | 없음 | 파일 출력·버전별 평가 추세 |

확장 WI는 기존 기반을 재사용한다. 일부 Vision/계약 WI는 implementing이며 전체 완료 조건은 미충족이다. 이미 있는 서버 기능을 모두 미구현이라고 해석하지 않는다. 현재 35개 WI 중 1개 done이라는 수치는 신규 계획의 작업 단위 상태이며 제품 완성도 퍼센트가 아니다.

## 직접 검증한 결과

- `cd backend && .venv/bin/python -m pytest -q`: **17 passed, 1 warning**, 0.31초. 경고는 Starlette TestClient의 httpx deprecation이다.
- 별도 임시 SQLite와 FastAPI TestClient에서 현재 API 13개 확인.
- ATC/Readback/Cockpit 모두 `confidence=0.0`, `observed_at=2020-01-01T00:00:00Z`, 값 일치 → **VERIFIED**. 모델 신뢰도와 관측 freshness가 현재 판정에 적용되지 않는다는 실행 근거다.
- `altitude=null` → **422**. 판독 불가 Observation 전달 미지원.
- heading만 전달 → **422**. 부분 지시 미지원.
- frontend/communication/tests/integration/scripts는 골격이다. 이후 추가된 Vision 정지 이미지 PoC와 계약 초안은 [Vision 검증 기록](../vision/evaluation/README.md) 참조: 테스트 13개, 합성 고정 기대 사례 5개 통과. 서버 전송·실장비는 미구현.
- 이전 실제 Uvicorn HTTP 시연 결과는 SPEC-001-WI-01 참조. 이번 추가 확인은 TestClient 검증이며 실제 카메라·마이크·통신 검증이 아니다.

## 다음 구현 순서

1. SPEC-002-WI-01: 판독 불가·부분 지시·품질·health·근거를 포함한 계약 확정.
2. 김세현: 태블릿 실제 프레임·ROI·정답 세트를 준비하고 현재 스트림의 실카메라 장애/복구·품질·지연을 검증한다. 이후 근거/서버 전송.
3. Backend: SPEC-002-WI-02와 SPEC-005로 계약 수신·stale 처리·3상태 판정.
4. 통신/음성과 UI를 연결한 뒤 중간점검 E2E를 별도 검증.

검토 범위는 이 저장소의 현재 체크아웃과 원격 dev/main이다. 팀원의 미푸시 코드나 다른 저장소의 작업은 포함하지 않는다.

## 공유 문서와 최종 Vision 검증

사용자 요청으로 사진·결과·재현 안내를 [MCP Vision 문서](vision/README.md)에 보존했다. 현재 Vision 테스트 29개 및 합성 고정 사례 5개 통과, 참고 사진 ALT 10000/HDG 270/speed 250 인식 확인. 중복 output 81개(약 8.7MB) 정리. 실제 카메라/서버 연동은 미구현이다.

## 태블릿 MCP와 Vision 스트림 추가 검증

2026-10-10 사용자 요청으로 실제 Cockpit 대신 태블릿 모의 MCP를 촬영하는 데모 범위를 SPEC-003 v2에 반영했다.

- 구현: frontend React/Vite 수동 MCP 화면(ALT/HDG/IAS·가림·촬영 모드), Vision snapshot/ROI 도구·영상/웹캠 입력·자동 재연결·독립 상태 감시·연속 안정화. 출력은 로컬 vision-stream/1이며 서버 계약은 그대로다.
- `vision/.venv/bin/python -m pytest vision/tests -q`: 45 passed. 실제 OpenCV 파일 디코딩 + mock 장치·결정론적 OCR 안전 경계 포함.
- `npm run build` (frontend): 통과. 브라우저 수동 입력·범위 거부·0/359·값 변경·가림·촬영 모드, 1024×768 가로 넘침 없음 확인.
- 구현 화면의 브라우저 캡처에서 실제 macOS OCR: ALT 3000/HDG 270/IAS 250. 실제 카메라 촬영 검증 아님.
- 무손실 합성 영상 12프레임: 정상→변경→ALT 가림→16000/0, 변경 직후 null·3회 안정화·가림 null·EOF 확인. 파일 UTC 촬영 시각 null/live_input=false 확인.
- MJPG 합성 영상: ALT 3500은 low_model_score로 보류. 사진/무손실 결과를 압축 영상 성능으로 일반화하지 않음.
- 미실행: 실제 태블릿/웹캠, ROI GUI 수동 선택, 반사·흐림 평가 세트, 서버 통합. backend 제품 코드를 바꾸지 않아 기존 backend 회귀는 이번에 재실행하지 않음. WI-01~03 implementing, WI-04~05 pending 유지.

재현과 다음 실장비 작업은 [태블릿 안내](../vision/docs/tablet-demo.md), 작업 기록은 [SPEC-003](spec/003-cockpit-vision.md)에 있다.

## SPEC-002-WI-01 계약 구현·PR 검토 · 2026-10-17

공통 v2 DTO, JSON Schema6종, fixture21개·manifest, 계약 검사 도구를 작성했다. backend 전체117개 테스트와 Schema/DTO 예제 검사를 통과했다. 현재 v1 OpenAPI/라우터는 유지한다. 작업은 PR 검토 중이며 v2 수신·DB·중복/시간 기반 상태 검사는 다음 WI 범위다. [검증 기록](spec/002-observation-contracts/workitem/wi-01.md)에 범위·명령·미실행 항목을 남겼다. 이 상태는 dev 기반 현재 PR의 검증 범위이며 다른 열린 PR의 구현 완료를 판정하지 않는다.

## v2 수신·저장·문맥 검사 · 2026-10-18

PR #5의 계약이 dev에 squash merge(`5515878`)됐다. 후속 SPEC-002-WI-02는 별도 브랜치에서 v2 세션·구간 등록/취소·관측/health·현재 상태·입력/Trace 조회를 구현했다. 설정은 비행별 snapshot으로 고정하며 미설정·stale·미상·저품질·이전 시도는 현재 정상 근거로 쓰지 않는다. 부분 목표의 출처, 늦은 Pilot의 동일 ATC 연결, 장애 복구 후 새 관측을 검사한다.

SQLite 추가 migration·기존 DB 보존·동시 중복·commit 실패 원자성 테스트를 포함해 backend172 passed, 경고1개. 계약 스키마6종·fixture21개 검사 통과. 기존 Mock 경로와 그 Trace 형태는 유지한다. v2 Trace는 별도 경로로 조회하며 최종 숫자 비교·규칙 판정·모델/실장비·통합 리포트는 아직 구현/검증하지 않았다. 상세 결과와 제약은 [WI-02](spec/002-observation-contracts/workitem/wi-02.md), 실행/API 계약은 [v2 수신 안내](../contracts/receiving-v2.md)를 따른다.

## 2026-10-18 SPEC-002-WI-03 계약 HTTP 통합

PR #6을 `aae3113`로 squash merge한 dev를 기준으로 독립 JSON 생산자와 실제 임시 uvicorn/SQLite를 연결했다. 통합21개·기존 backend174개·Schema6종/fixture21개 검사 통과. 0/null·부분 지시 출처·미인식·장애 복구·새 목표/프레임·잘못된 버전/단위/연결·중복·시도 순서·실행 격리와 원본/Trace 대응을 검증했다. 상세 근거·실행 안내·미실행 범위는 [WI-03](spec/002-observation-contracts/workitem/wi-03.md)을 따른다. 실제 카메라·STT/OCR·최종 판정·알림·리포트 연동 성공을 뜻하지 않는다.

## 2026-10-18 SPEC-005-WI-01 결정론적 구조화 검사

PR #7의 자동 리뷰가 head7bd3544에 대해 지적 없이 완료된 것을 확인하고 d46c3ac로 squash merge한 dev에서 진행했다. 모델 PASS와 서버 규칙 결과를 분리해 원문/필드 raw_text·HDG/명시 FL·등록 호출부호/구간·시각 순서·명시 상한/급변 정책을 검사한다. 비PASS 입력은 목표/현재 숫자에 적용하지 않고 원본과 해당 관측의 규칙 근거를 같은 수신 트랜잭션으로 저장한다. 새 정책·결과 Schema2종과 문형 fixture20개, backend251개·실제 HTTP24개 검증 근거를 추가했다. 실제 모델/장비·최종 3상태/타이머/알림/Incident는 미검증/후속 범위이며 v2 전체 결과는 계속 UNVERIFIED다. 상세 구현·검증·리뷰·인수인계는 [WI-01](spec/005-safe-validation/workitem/wi-01.md)을 따른다.

## 2026-10-18 SPEC-005-WI-02 3상태·오류 단계

PR #8 리뷰 P2를 수정·검증해525f98a로 병합한 기준에서 READBACK/SETTING별 NORMAL/MISMATCH/UNVERIFIED·대표 단계·안내 후보를 구현했다. 복창 확인 최초5초·조기 전체 일치·이후 재불일치 즉시 확인, ALT 부분 변경 시 기존 HDG 감시와 최신 지시/복창 대기 전환을 분리한다. 판정·타이머/완료 기록·Trace는 수신과 원자 저장하고 GET은 사본에서 기한/만료를 재평가한다. backend288/HTTP26·계약 검사·미실행 범위는 [WI-02 MD 하단 결과](spec/005-safe-validation/workitem/wi-02.md)를 따른다. 실제 음성·Incident 해결·장비/모델/전체 E2E는 후속 범위다.

## 2026-10-18 SPEC-005-WI-03 판정 전체 회귀·거짓 정상 검증

PR #9 문서 리뷰 P2 수정·병합b3262cf를 기준으로 순수3상태 필드 조합81개와 수신/API 설정9개·불확실성12개·혼합 복창·legacy RESOLVED 격리·지연 입력 회귀를 추가했다. 실제 HTTP11개를 추가해 backend393/HTTP37·공통 계약 검사와 반복 실행 ID 격리를 확인했다. 이 WI에서 제품 코드·정책·Schema는 변경하지 않았다. 유한한 합성 회귀 범위의 결과이며 실제 모델 정확도·장비 E2E 성공으로 표현하지 않는다. 상세 AC별 근거·초기 실패 수정·리뷰·인수인계는 [WI-03 MD 하단 결과](spec/005-safe-validation/workitem/wi-03.md)를 따른다.
