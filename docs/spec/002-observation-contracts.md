# SPEC-002: 관측 계약과 지시 연결

## 기본 정보

- 요구사항 버전: 1
- 상태: draft (목표 초안; 현재 구현과 미정 사항은 별도 표시)
- Priority: P0
- 근거: [서비스 방향](../service/overview.md), [요구사항 매핑](../service/requirements-map.md)
- 기능 전체 검증: SPEC-002-WI-03 (SPEC-010은 서로 독립된 두 선택 기능이므로 각 WI 자체 검증)

## 목적과 범위

파트가 공통 단위·지시 ID·품질·근거로 데이터를 주고받는다.

포함 범위는 아래 workitem의 산출물이다. 실제 항공기 제어·QNH/Baro와 다른 기능의 소유 계약은 제외한다. 2026-10-13 사용자 요청으로 WI-01의 계약 코드·예제를 구현한다. WI-02는 서버 수신·추가 DB 저장을 구현한다. 최종 판정 로직은 SPEC-005 범위다.

## 동작·계약·미정 사항

공통 단위·ID·시각·null·품질·근거는 [SPEC-002](002-observation-contracts.md), 판정은 [SPEC-005](005-safe-validation.md)를 따른다. 해당 계약 확장 전 현재 API가 지원한다고 가정하지 않는다.
미정 사항 Q-01~Q-05와 영향 범위는 [서비스 방향](../service/overview.md#결정이-필요한-항목)에 있다. workitem의 선행 결과와 필수 결정이 확보된 범위만 구현한다. fixture 성공과 실카메라·마이크·수신 성공을 구분한다.

## 이미 구현된 기반

기존 Mock 경로에는 기본 Observation DTO, endpoint별 source, clearance_id 연결, 입력 순서/중복 거부가 있다. WI-01/02로 별도 v1 경로에 null·부분 지시·quality/health/evidence·버전·시각 검사를 추가했다. 상세 실행 근거는 [구현 현황](../IMPLEMENTATION_STATUS.md)을 참조한다. 아래 WI는 확장 요구까지 포함하므로 이 기반만으로 done 처리하지 않는다.

## 완료 조건

| ID | 입력·전제와 관찰 가능한 기대 결과 | 검증 | 담당 workitem |
| --- | --- | --- | --- |
| AC-01 | 선행: SPEC-001-WI-01. ALT/HDG 부분 지시, null 사유, UTC 촬영/처리 시각, source, 지시 연결, 채널 상태, 필드별 점수·품질·근거 참조를 버전 계약과 정상/실패 예제로 정의한다 | 스키마 예제 검증; 기존 필수 Observation과 확장 호환성 대조 | [SPEC-002-WI-01](#wi-01) |
| AC-02 | 선행: SPEC-002-WI-01. 최초 입력·수정 입력·health를 수신하고 stale/다른 지시/중복/역순 입력이 잘못된 VERIFIED 또는 RESOLVED를 만들지 않는다 | 현재 API 회귀와 새 계약·연결·freshness 경계 테스트; DB 변경은 재현 가능한 마이그레이션 | [SPEC-002-WI-02](#wi-02) |
| AC-03 | 선행: SPEC-002-WI-02. mock 생산자와 backend가 정상/부분 지시/미인식/장애/새 지시/재검증 예제를 동일한 의미로 처리한다 | 버전·단위·null·타임스탬프 계약 통합; 실제 입력 성공은 별도 기록 | [SPEC-002-WI-03](#wi-03) |

## Work items

진행 상태의 원본은 [TODO](todo.md)다. 아래 담당자는 기획 역할 기준 제안이며 작업 예약은 아니다.

<a id="wi-01"></a>

### SPEC-002-WI-01: 공통 관측·품질·근거 계약 정의

- Priority: P0; 담당 제안: 공통
- 완료 조건: AC-01
- 선행 작업·산출물: SPEC-001-WI-01
- 수정 영역: `contracts/, backend/app/schemas/`
- 산출물·개별 완료 조건: ALT/HDG 부분 지시, null 사유, UTC 촬영/처리 시각, source, 지시 연결, 채널 상태, 필드별 점수·품질·근거 참조를 버전 계약과 정상/실패 예제로 정의한다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 스키마 예제 검증; 기존 필수 Observation과 확장 호환성 대조
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

- 구현: 2026-10-13 사용자 요청으로 공통 `radar-observation/1` 계약 작성. [계약 문서](../../contracts/observation-v1.md), [구조 스키마](../../contracts/schemas/observation-v1.schema.json), `backend/app/schemas/observation_contract.py`, `contracts/examples/observation-v1/`의 6개 예제와 `backend/tests/test_observation_contract.py` 추가. 기존 DTO·API·Vision 생산자는 변경하지 않음. `python` 브랜치 `6ca59c5`로 커밋·origin/python 푸시 완료.
- 검증: backend에서 임시 가상환경 Python 3.13 / Pydantic 2.14.1로 `python -m pytest -q` 실행. 최종 **54 passed, 1 warning**(Starlette/httpx deprecation). 마지막 타입 제약 수정 후 배포 스키마 불일치가 1회 탐지되어 재생성했고 최종 전체 검사를 통과함. `git diff --check` 및 변경 문서의 로컬 링크 검사 통과. 정상/부분 지시/판독 불가/시각 미상/수정/health 예제와 범위·UTC·근거·연결 실패, 배포 스키마 일치, 기존 ObservationInput 비호환 경계 확인.
- 리뷰: 단일 에이전트가 역할 지침으로 검토. partial 필드 null과 판독 실패 value=null 구분, 0도 보존, unavailable 숫자 거부, 원본 sample ID와 관측 ID 분리, score를 확률로 표현하지 않는지 확인. JSON Schema만으로 교차 필드 검사를 대체할 수 없음을 문서화. 팀 합의·실제 생산자 호환성을 확인했다고 주장하지 않음.
- 인수인계: WI-02에서 지시 ID 예약/생성·수신·DB·중복/역순/freshness 검사를 구현하고 WI-03에서 생산자 어댑터를 통합 검증. Q-04 임계값은 미정으로 유지하며 구조 계약 완료를 차단하지 않음. 실제 카메라/마이크/SDR, HTTP 새 계약 수신은 미실행. 사용자 `.gitignore` 변경 보존.

<a id="wi-02"></a>

### SPEC-002-WI-02: 백엔드 수신·지시 연결과 중복/지연 처리

- Priority: P0; 담당 제안: 노남경
- 완료 조건: AC-02
- 선행 작업·산출물: SPEC-002-WI-01
- 수정 영역: `backend/app/api/, schemas/, services/, models/`
- 산출물·개별 완료 조건: 최초 입력·수정 입력·health를 수신하고 stale/다른 지시/중복/역순 입력이 잘못된 VERIFIED 또는 RESOLVED를 만들지 않는다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 현재 API 회귀와 새 계약·연결·freshness 경계 테스트; DB 변경은 재현 가능한 마이그레이션
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

- 구현: 2026-10-13 사용자 후속 요청으로 WI-02 진행. `backend/app/api/contract_observations.py`, `services/contract_service.py`, `models/contract_observation.py`, `app/migrate_contract_storage.py`, `app/main.py`, `tests/test_contract_receiving.py` 및 [API 안내](../../contracts/observation-api-v1.md) 추가/갱신. `python` 브랜치 `69f2f38`에 커밋된 선행 구현. `/api/v1` 지시 예약·관측/수정/health 수신·상태/이력 조회 구현. 기존 Mock DTO·테이블·API 보존. 최신 포인터와 입력 이력을 같은 트랜잭션으로 저장.
- 검증: backend에서 `/private/tmp/radar-contract-venv/bin/python -m pytest -q`: **70 passed, 1 warning**(Starlette/httpx deprecation). 기존 54개+새 16개: 부분 지시/0도/null/수정·중복/동시 재시도·시각 미상/미래/stale 경계·역순·다른 비행/대체 지시/종료·health·마이그레이션 2회·실패 커밋 원자성 확인. OpenAPI의 신규 4개 경로·ObservationContract 요청 스키마 확인. TestClient·임시 SQLite 검증이며 실장비/실제 외부 HTTP·다른 DB는 미실행. `git diff --check`·문서 로컬 링크 검사 통과.
- 리뷰: 단일 에이전트가 역할 지침 적용. 동일 sample 재사용·잘못된 이전 수정 참조 거부, ATC 수정 시 종속 관측 제거, 거부된 미래 입력의 watermark 오염 방지, 시각 미상 값의 정상 처리 방지 확인. 수신 accepted와 최종 판정 분리: 새 v1 경로는 UNVERIFIED/validation_pending을 유지하며 SPEC-005 이전에 VERIFIED/RESOLVED를 만들지 않음. 기존 legacy Mock 경로의 confidence/freshness 미지원은 그대로이며 실입력에는 사용하지 않음.
- 인수인계: 다음 WI-03에서 mock 생산자·소비자 공통 예제를 통합 검증. SPEC-005에서 규칙·3상태 판정, SPEC-007에서 Incident/해결, SPEC-008에서 통합 Trace를 구현. 임시 30초 age 기본값은 설정 가능하며 Q-04 팀 확정·실장비 평가를 뜻하지 않음. 기존 사용자 `.gitignore` 변경 보존. 후속 확인 시 WI-02 커밋 `69f2f38`이 현재 체크아웃에 존재함; 원격 푸시 여부는 이번 작업에서 검증하지 않음.

<a id="wi-03"></a>

### SPEC-002-WI-03: 생산자·소비자 계약 통합 검증

- Priority: P0; 담당 제안: 공통
- 완료 조건: AC-03
- 선행 작업·산출물: SPEC-002-WI-02
- 수정 영역: `contracts/examples/, tests/integration/`
- 산출물·개별 완료 조건: mock 생산자와 backend가 정상/부분 지시/미인식/장애/새 지시/재검증 예제를 동일한 의미로 처리한다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 버전·단위·null·타임스탬프 계약 통합; 실제 입력 성공은 별도 기록
- 기능 전체 검증: 예; 이 스펙의 모든 AC를 대조하되 환경과 mock/실입력을 구분한다.

#### 결과·검증·리뷰·인수인계

- 구현: 2026-10-13 후속 요청으로 `tests/integration/mock_contract_producer.py`, `conftest.py`, `test_contract_producer_integration.py`, [통합 검증 안내](../../tests/integration/README.md) 추가. 원본 계약 예제 6개 재사용. `python` 브랜치 `69f2f38` 기준 미커밋 변경이며 제품 코드·원본 예제는 수정하지 않음.
- 검증: backend에서 `/private/tmp/radar-contract-venv/bin/python -m pytest tests ../tests/integration -q`: **84 passed, 1 warning**(Starlette/httpx deprecation), 기존 70개와 통합 14개 통과. Mock→JSON API→임시 SQLite→상태/이력 조회 경계에서 정상 3source·부분 지시/null/0도·미인식·시각 미상·health·새 지시·새 샘플 수정·버전/단위/사유 위반·UTC 재시도 의미 확인. 초기 테스트 이름 충돌은 통합 테스트 파일명 변경으로 해결했고 +00:00/Z 문자열 비교 실패는 같은 시각의 의미 비교로 수정함. `git diff --check` 및 로컬 문서 링크 검사 통과.
- 리뷰: 단일 에이전트가 역할 지침 적용. Mock 생산자는 서버 스키마를 import하지 않고 독립 JSON을 전송함. 원본 예제의 값·품질·실패 사유·근거를 유지하고 새 합성 샘플에만 ID/시각을 부여함. health가 새 관측/해결을 만들지 않는지, 이전 지시 관측이 새 지시에 복사되지 않는지, 수정 전후 이력과 UTC 정규화 의미를 확인함. AC-01은 기존 스키마/예제 검사, AC-02는 기존 수신/마이그레이션 검사, AC-03은 새 통합 14개로 전체 대조.
- 인수인계: SPEC-002의 Mock 계약 검증 완료. 실제 카메라·마이크·SDR·OCR/STT 어댑터, 실제 외부 HTTP 서버와 다른 DB 검증은 미실행. v1 상태는 SPEC-005 구현 전 UNVERIFIED/validation_pending 유지. 다음 구현은 SPEC-005-WI-01 규칙 재검증이며 실제 생산자 연동은 SPEC-003/004에서 진행. 커밋/푸시 미실행, 사용자 `.gitignore` 변경 보존.

## 변경 기록

- v1 · 2026-10-10: 사용자 제공 기획·Priority·자문과 현재 코드로 최초 작업 초안 작성. 문서 작성 권한과 기능 구현 권한은 구분한다.

- 2026-10-13: SPEC-002-WI-01 공통 버전 계약·예제·호환성 검증 추가. 요구사항 변경 없이 AC-01 구현; 서버 수신은 WI-02 범위.

- 2026-10-13: SPEC-002-WI-02 v1 수신·지시 예약·연결·중복/시각 경계·추가 DB 마이그레이션 구현. AC-02 완료, 최종 판정은 SPEC-005로 분리.

- 2026-10-13: SPEC-002-WI-03 독립 Mock 생산자·JSON API 통합 검증 14개와 실행 안내 추가. AC-01~03 Mock 범위 완료, 실입력 성공으로 해석하지 않음.
