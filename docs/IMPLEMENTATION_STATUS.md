# RADAR 구현 현황

확인일: 2026-10-17. 현재 `python` 브랜치의 미커밋 확장을 포함한다. 최신 실행/제한은 [운영 안내](development/operations.md)와 각 스펙의 2026-10-17 기록을 따른다.

| 영역 | 최신 코드와 남은 인수 |
| --- | --- |
| 환경·계약·판정 | 공통 설치/CI·v1 관측·명시 정책·3상태·안전 회귀 구현 |
| Vision | 기존 카메라/ROI/OCR + 근거/서버/correction 어댑터; 실제 태블릿 카메라 전체 경로 미검증 |
| 음성 | ATC WAV/Pilot 마이크·로컬 faster-whisper·구간/품질·보수적 구조화·서버 전송; 실제 마이크/정답 교신 인수 미실행 |
| 운영 UI | /operations 서버 판정·근거·확인·선택 음성/억제·연결 실패 보류; Chromium fixture 검증, 실제 교신/음성 출력 미검증 |
| Closed-loop·Report | 사건/수정/해결·확장 Trace·근거 수명주기·종료 리포트·JSON 출력 구현; 실입력 전체 시연 미실행 |
| 평가 | 합성 프로토콜·분모/지연/실패 보고·동일 세트 버전 비교·합성 HTTP 리허설; 실제 독립 평가·발표 장비 인수 미실행 |

로컬 검증: Backend/통합 215개·Vision 45개, Frontend 빌드·Chromium 2개·실제 HTTP legacy/v1 합성 시연 통과. 추가 변경 후 최종 결과는 아래 후속 기록에 남긴다. Whisper tiny.en 합성 WAV에서 오인식이 발생했고 보류됨을 확인했으며 정확도 통과로 보고하지 않는다. 원격 CI는 아직 실행하지 않았다.

## 초기 기준선 기록 (아래는 2026-10-10 당시 상태)

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

## 공통 계약 수신 추가 — 2026-10-13

SPEC-002-WI-01 계약은 `6ca59c5`로 origin/python에 공유했다. WI-02는 현재 체크아웃의 `69f2f38`에 구현되어 있으며 [v1 API](../contracts/observation-api-v1.md)에서 지시 예약·관측/수정/health 수신·시각/중복/연결 검사·상태/이력 조회를 제공한다. legacy Mock 경로·테이블은 보존하고 추가 저장소를 사용한다. 신규 v1 입력은 항상 UNVERIFIED/validation_pending으로 표시하며 최종 판정은 SPEC-005 범위다. 실제 생산자·장치 연결은 미검증이다. 실행 결과와 남은 결정은 [WI-02](spec/002-observation-contracts.md#wi-02)에 기록한다.

2026-10-13 WI-03에서 독립 Mock 생산자의 JSON API 통합 검증을 추가했다. SPEC-002의 Mock 범위 AC-01~03을 대조했으며 실장비/모델 어댑터 검증과 최종 판정은 미완료다. 재현은 [통합 검증 안내](../tests/integration/README.md), 결과는 [WI-03](spec/002-observation-contracts.md#wi-03)에 기록한다.

## 결정론적 구조화 검사 — 2026-10-13

SPEC-005-WI-01에서 [검사 함수·정책](../contracts/extraction-rules.md)을 추가했다. HDG/FL/원문 값/확인 문맥/급변을 PASS·INVALID·NEEDS_REVIEW로 검사한다. 함수 구현만 완료했으며 API 상태는 아직 UNVERIFIED/validation_pending이다. 최종 3상태 판정 연결은 WI-02 범위다. 모의 정책은 실장비 운용 기준이 아니며 결과와 검증 범위는 [WI-01](spec/005-safe-validation.md#wi-01)에 기록한다.

## 3상태 판정 연결 — 2026-10-14

SPEC-005-WI-02에서 [명시 설정·3상태 판정](../contracts/three-state-validation.md)을 v1 서버에 연결했다. 설정·확인 문맥·fresh/가용/검증된 입력이 있어야 NORMAL이며, 확인된 Readback/Setting 숫자 불일치는 MISMATCH, 불충분 근거는 UNVERIFIED다. 설정이 없는 기존 v1 입력은 계속 보류한다. 단계별 rules/비교·사유와 확인 주체/정책을 조회할 수 있다. Readback만 해결된 RESOLVED와 전체 NORMAL을 구분하고 장치 장애 후 새 관측을 요구한다. 이번 변경은 미커밋이며 실행 근거·미실행 범위는 [WI-02](spec/005-safe-validation.md#wi-02)에 기록한다. 전체 기능 검증 WI-03과 실장비 인수는 별도다.

## 설치·검증 기반과 판정 전체 회귀 — 2026-10-16

SPEC-001-WI-02/03에서 [공통 설치·실행·설정·검증 안내](development/README.md), Python/Node 기준·의존성 고정, 로컬 명령/CI를 추가했다. SPEC-005-WI-03은 [AC별 안전 회귀](../tests/integration/validation-coverage.md)를 추가해 모의 범위 전체 검증을 완료했다. 실제 설치/실행·명령 결과·원격 CI/실장비 미실행 근거는 각 workitem에 기록한다. 새로운 제품 기능·실제 생산자 연동을 구현했다고 해석하지 않는다. 이번 변경은 `python` 브랜치의 미커밋 상태다.

## 2026-10-17 최종 검증

Backend/계약/통합 215개·Vision 45개, Frontend 빌드·Chromium 2개, 실제 HTTP legacy/v1 네 합성 시나리오·리포트 출력 통과. 브라우저는 즉시 연결 실패 및 응답이 멈춘 경우(5초 제한) 모두 기존 정상 배지를 제거하고 재연결을 확인했다. 평가 CLI의 12개 합성 all-hold 예측/두 fixture 버전 비교는 도구 동작 확인이며 실제 모델 성능 평가가 아니다. 전체 변경 미커밋. 실행/제약은 운영 안내 참조.

2026-10-17: 후속 구현을 기능별 6개 코드/테스트 커밋과 별도 문서 커밋으로 보존했다. 앞선 미커밋 표기는 당시 기록이다. [커밋 인수인계](spec/todo.md#2026-10-17-단계별-커밋-기록)를 따른다.
