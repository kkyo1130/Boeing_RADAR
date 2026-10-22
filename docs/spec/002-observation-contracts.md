# SPEC-002: 관측 계약과 지시 연결

## 기본 정보

- 요구사항 버전: 6
- 상태: draft (목표 초안; 현재 구현과 미정 사항은 별도 표시)
- Priority: P0
- 근거: [서비스 방향](../service/overview.md), [요구사항 매핑](../service/requirements-map.md)
- 기능 전체 검증: SPEC-002-WI-03

## 목적과 범위

파트가 공통 단위·지시 ID·품질·근거로 데이터를 주고받는다.

포함 범위는 아래 workitem의 산출물이다. 실제 항공기 제어·QNH/Baro와 다른 기능의 소유 계약은 제외한다. WI-01 계약과 WI-02 수신·저장·연결·시간 검사를 구현했다. 최종 숫자 비교와 3상태 판정·음성 모델·실장비 통합은 후속 WI 범위다.

## 동작·계약·미정 사항

공통 단위·ID·시각·null·품질·근거는 [SPEC-002](002-observation-contracts.md), 판정은 [SPEC-005](005-safe-validation.md)를 따른다. 해당 계약 확장 전 현재 API가 지원한다고 가정하지 않는다.
사용자 결정 R-01~03은 [서비스 방향](../service/overview.md)에 반영됐다. 아래 기술안은 구현 계획이며 사용자 발언이나 구현 완료를 뜻하지 않는다. 측정할 설정값은 해당 WI에서 근거와 함께 정한다. fixture 성공과 실장비 성공은 구분한다.

## 확장 계약 기술안

WI-01에서 [공통 계약 v2](../../contracts/observation-v2.md), Pydantic DTO, JSON Schema 6종과 정상·실패 예제를 작성·검증했다. 이 계약은 후속 구현의 기준이며 현재 `/api` 라우터가 v2를 수신한다는 뜻은 아니다. 실제 필드·교차 검증의 원본은 계약 문서와 DTO를 따른다.

| 정보 | 타입·필수 여부 | 의미·제약 |
| --- | --- | --- |
| 계약 버전 | 문자열, 필수 | 생산자·서버가 지원하는 버전. 미지원 버전은 명시적으로 거부하며 성공 관측으로 저장하지 않음 |
| 관측 ID·비행 ID | 문자열, 필수 | 관측 ID는 재전송 때 동일하게 유지. 다른 비행의 관측을 현재 비행에 적용하지 않음 |
| 입력 출처 | ATC / READBACK / COCKPIT, 필수 | 서버 경로·생산자 계약과 일치해야 함. 음성의 역할 제어 근거는 별도 보존 |
| 입력 구간 ID·처리 시도 ID | 음성에서 필수 | ATC 결과 완료 순서가 아니라 수음 구간에 Pilot을 연결. 재시도는 새 시도로 구분하고 이전 시도의 늦은 결과를 배제 |
| 관측 시각·처리 완료 시각 | 명시적 UTC 필드, 관측 시각은 미상일 때 null | time_basis와 미상 사유를 함께 전달. 처리·파일 수정 시각으로 촬영 시각을 채우지 않음. 서버 수신 시각과 freshness는 수신 서비스가 검사 |
| ALT | 정수 feet 또는 null | 값은 0 이상. 판독 불가·누락을 0으로 치환하지 않음 |
| HDG | 정수 0–359 또는 null | 0은 유효한 북쪽 값. 범위 밖 입력을 임의 보정해 정상화하지 않음 |
| 항목 존재·유효성·사유 | 항목별 필수 | 지시에 포함되지 않은 항목과 포함됐으나 해석 실패한 항목을 구분. 후자를 기존 목표로 채워 부분 지시로 채택하지 않음 |
| 호출부호·정규화 결과 | ATC/READBACK에서 필수, 해석 실패 시 null+사유 | 등록된 별칭만 대상 호출부호로 정규화. 원본 문자열 보존. 다른 대상의 확실한 지시는 근거만 저장 |
| 모델 점수·입력 품질 | 항목별 선택 값 및 평가 불가 사유 | 점수는 정확도가 아님. 점수 누락을 고품질로 처리하지 않음 |
| 채널 상태 | channel_health 필수, 별도 HealthEvent 가능 | 정상 수신·판독 불가·장치 연결 끊김을 구분. health 이벤트는 수치 관측 없이 전송 가능 |
| 근거 참조 | 원본/구간/ROI 참조 또는 미확보 사유 | 실시간 근거 조회용 선택 참조. R-02에 따라 종료 리포트는 구조화 값만으로 완성; 미디어 부재가 조회 실패는 아님 |
| 적용 목표 | 서버가 항목별 관리 | ALT와 HDG 각각 목표값·원본 지시 ID·적용 버전을 보존. 수신한 원본 추출값을 수정해 만들지 않음 |

### 수신·적용 순서

1. 버전·형식·범위·비행 연결을 검사한다. 형식 오류는 거부 결과를 반환하고 유효 관측으로 판정하지 않는다.
2. 관측 ID 중복과 처리 시도·지시 연결을 검사한다. 같은 ID·같은 내용 재전송은 기존 처리 결과를 반환하고 이벤트를 중복 생성하지 않는다. 같은 ID·다른 내용은 충돌로 거부한다.
3. 원본과 처리 근거를 보존하고 관측 시각·채널 상태·항목 유효성을 검사한다. stale·역순·취소된 시도는 최신 판정을 덮어쓰지 못한다.
4. 유효한 새 ATC만 해당 항목의 목표를 변경한다. Readback은 그 지시의 명시 항목을 비교하고 Cockpit은 현재 항목별 목표를 감시한다.
5. 판정은 SPEC-005, 수정·해결은 SPEC-007에서 수행한다. 수신 성공만으로 VERIFIED/RESOLVED를 만들지 않는다.

### 계약 검증 사례

| 사례 | 입력 | 기대 결과 |
| --- | --- | --- |
| 부분 변경 | A: ALT 3000/HDG 270 → B: ALT 4000만 명시 | 목표 ALT=B/4000, HDG=A/270. B의 복창 요구는 호출부호와 ALT 4000 |
| 해석 실패 | B에 고도 언급은 있으나 값 추출 실패 | 정상적인 ALT 생략으로 취급하지 않고 판단 보류. 이전 값으로 B를 보충하지 않음 |
| 유효한 0 | 최신 HDG=0, 판독 성공 | 유효한 값으로 비교; null과 구분 |
| 장치 장애 | 카메라 연결 끊김, 수치 없음 | health 처리와 확인 불가 표시; 마지막 수치로 정상 유지 금지 |
| 재전송 | 동일 관측 ID·동일 내용 두 번 | 관측·상태 전이·알림이 중복 발생하지 않음 |
| 늦은 결과 | 이전 시도 결과가 재시도 이후 도착 | 이전 결과가 새 시도·목표·해결 상태를 덮어쓰지 않음 |
| 오래된 관측 | 설정 수정 이전 프레임으로 재검증 | 수정 완료로 인정하지 않음; 새 관측 필요 |

freshness 한도·시계 허용 오차는 실측으로 정할 설정값이다. 확정 전 테스트는 명시한 가상 시각·한도를 사용하고 해당 수치를 제품 확정값으로 보고하지 않는다. 현재 필수 ALT/HDG DTO를 nullable로 바꾸는 것만으로 확장 계약을 완료 처리하지 않는다. 버전·경로·응답 의미와 현재 OpenAPI와의 호환성은 WI-01 계약에 기록했다. WI-02는 [수신 계약](../../contracts/receiving-v2.md)에 따라 추가 테이블 마이그레이션과 수신 상태 검증을 구현했다.

## 부분 변경 지시의 항목별 출처

SPEC-007 D-007-04에 따라 현재 적용하는 ALT·HDG의 목표값과 원본 지시 ID를 항목별로 구분한다. ALT만 변경된 새 지시와 기존 HDG 지시의 출처를 하나의 새 지시로 덮어쓰지 않는다. 예: 지시 A의 ALT 3000ft·HDG 270° 이후 지시 B의 ALT 4000ft를 채택하면 ALT는 B, HDG는 A를 근거로 유지한다. 원본 음성의 추출 결과와 현재 적용 기준은 구분하며 새 음성에서 누락·판독 불가인 값을 기존 값으로 채우지 않는다. 관측은 각 항목의 적용 기준·유효성과 연결해 검증한다. 아래 버전 계약 기술안을 WI-01에서 스키마로 검증하며 현재 구현이 지원한다는 뜻은 아니다. AC-01, WI-01에 적용한다.

## 이미 구현된 기반

기본 Observation DTO, endpoint별 source, clearance_id 연결, 입력 순서/중복 거부가 있다. null·부분 지시·quality/health/evidence·버전·freshness 확장은 없다. 상세 실행 근거는 [구현 현황](../IMPLEMENTATION_STATUS.md)을 참조한다. 아래 WI는 확장 요구까지 포함하므로 이 기반만으로 done 처리하지 않는다.

## 구현 계약과 처리 기준

### 현재 API와 확장 경계

WI-01 산출물: [DTO](../../backend/app/schemas/observation_v2.py), [Schema·예제 검사](../../contracts/check_v2.py), [호환성·의미 계약](../../contracts/observation-v2.md). JSON Schema는 구조 검증, DTO는 시간·필드·출처 관계를 추가 검증한다. WI-02는 최신성·등록 목록·저장 상태에 따른 수신 적격성을 검사한다. 최종 비교 판정은 SPEC-005의 책임이다.

현재 `backend/app/schemas/observation.py`는 ALT·HDG·confidence 필수, 추가 필드 금지다. `observed_at` 생략 시 서버 시각을 사용하므로 실제 촬영 freshness를 증명하지 못한다. 확장에서는 원본 시각과 time_basis를 명시하며 미상은 null+사유로 기록한다. 기존 요청에 임의의 원본 시각을 만들어 넣지 않는다.

| 경로 그룹 | 현재 동작 | 확장 시 처리 |
| --- | --- | --- |
| `/api/flights/start`, `/{flight_id}/end` | 세션 생성·종료, 중복 종료 409 | 호출부호 등록 검사와 종료 후 작업 취소를 추가하되 기존 세션 조회 유지 |
| `/api/flights/{flight_id}/clearances` | 완전한 ATC 수치로 생성·목록 조회 | 부분 지시·항목별 출처·시도 ID는 별도 버전 계약으로 수용 |
| `/api/clearances/{id}/readback`, `/cockpit` | 최초 입력, 중복·순서 오류 409 | 반복 관측과 최초 제출을 구분. 기존 endpoint를 무조건 반복 호출하지 않음 |
| 위 경로의 `/reverify` | 오류 상태에서 수정 입력 | 새 관측·취소된 시도 검사와 지속 감시 경로 추가 |
| `/api/flights/{flight_id}/safety-trace` | 서버 이벤트 순 조회 | 필드별 판정·보류·대체·음성 완료 이벤트 추가 |

확장 기술안은 `/api/v2` 네임스페이스에서 세션, 음성 구간, 관측, health, 상태 조회를 분리하는 것이다. WI-01에서 요청/응답 JSON Schema와 endpoint 목록을 확정하고 WI-02가 구현한다. 기존 `/api` DTO를 묵시적으로 다른 의미로 바꾸지 않는다. v1은 기존 Mock 경로로 유지하며 실제 확장 기능을 지원하는 것처럼 표시하지 않는다.

응답 기술안: 생성 201, 조회·동일 요청 재전송 200, 모르는 자원 404, 종료 세션·ID 내용 충돌 409, 형식·범위·미지원 버전 422. 유효한 health/판독 불가 관측의 수신은 성공이며 이후 판정이 UNVERIFIED인 것과 HTTP 오류를 구분한다. 비동기 작업 접수는 202와 작업 ID를 반환하고 최종 성공을 뜻하지 않는다.

### v2 요청·응답 계약과 후속 endpoint 계획

공통 관측·health·음성 구간·목표·접수·오류 DTO와 예제는 [공통 계약 v2](../../contracts/observation-v2.md)에 정의했다. 관측·health·세션·구간 등록·state/이력 조회는 [수신 계약](../../contracts/receiving-v2.md)에 구현됐다. 아래의 리포트·음성 재생 등 미등록 경로는 후속 계획이다. 세션·완전한 UI snapshot·비동기 작업·리포트·재생 기록 DTO는 해당 WI에서 추가한다. 기존 v1 route·DTO는 유지하고 v2 route를 별도 등록했다. 아직 v1 세션을 v2로 자동 변환하지 않는다.

| 메서드·경로 | 입력 | 출력·주요 실패 |
| --- | --- | --- |
| POST `/api/v2/flights` | `callsign` 등록값 | 201 `flight_id`, `status`, `revision`; 미등록 422 |
| POST `/api/v2/flights/{id}/end` | 활성 비행 | 200 종료 snapshot, 중복 종료409 |
| POST `/api/v2/flights/{id}/speech-segments` | SpeechSegmentV2 | 201 구간 등록·instruction_id 예약, 동일 재전송200. 실제 STT 작업 큐·202 응답은 SPEC-004 후속 범위 |
| POST `/api/v2/flights/{id}/observations` | 아래 관측 envelope | 201 접수 또는 동일 재전송200, 내용 충돌409 |
| POST `/api/v2/flights/{id}/health-events` | `schema_version`, `flight_id`, `event_id`, `channel`, `observed_at`, `health` | 201 접수; 수치 관측 필수 아님 |
| GET `/api/v2/flights/{id}/state` | 비행ID | 200 `revision`, `targets`, `readback`, `setting`, `health`, `input_permissions`, `advisories`; 없음404 |
| POST `/api/v2/flights/{id}/advisory-playbacks` | `advisory_id`, `playback_attempt_id`, `outcome`, `occurred_at` | 201 재생 기록; 중복200·다른 내용409. outcome은 completed/interrupted/failed |
| GET `/api/v2/flights/{id}/report` | 종료된 비행ID | 200 구조화 리포트; 미종료409·없음404 |

[판독 불가 관측 예제](../../contracts/examples/v2/cockpit-unreadable.json)는 필드별 quality·raw_text·validity와 명시적 미디어 부재 사유를 포함한다. [부분 변경 목표 예제](../../contracts/examples/v2/targets-partial.json)는 ALT 출처 B/4000, HDG 출처 A/270 및 B의 ALT만 요구하는 복창 범위를 보존한다. 전체 예제와 구조/교차 검증 기대값은 [manifest](../../contracts/examples/v2/manifest.json)를 따른다.

`target_revision`은 생산자가 알고 있던 서버 목표 버전이며 지시 소유권·최신성 판정을 대신하지 않는다. 음성의 mentioned_fields와 fields 키는 일치해야 하고, 실제 생략과 추출 실패는 각각 키 생략/명시적 null로 구분한다. UNKNOWN 명시 범위·실패 호출부호를 PASS로 바꾸지 않는다.

body의 `flight_id`와 URL ID, 관측 시각·수신 시각·현재 목표·시도 ID의 대조는 WI-02가 구현했다. Schema 통과·접수 응답만으로 VERIFIED/RESOLVED를 만들지 않는다. 카메라 DISCONNECTED의 health는 수치 없이 전달하며 현재 상태의 마지막 숫자를 정상 근거로 재사용하지 않는다.

### 저장과 순서

관측 스냅샷·현재 상태·Safety Trace를 하나의 트랜잭션으로 갱신한다. event ID는 정렬·중복 제거의 기준이고 observed_at은 원본 발생 시각이다. 동일 타임스탬프는 서버 event ID로 정렬한다. 실패한 트랜잭션은 상태만 바뀌거나 이벤트만 남지 않아야 한다. DB 변경은 이전 데이터가 있는 복사 DB에서 마이그레이션 후 조회 회귀로 확인한다.

## 완료 조건

| ID | 입력·전제와 관찰 가능한 기대 결과 | 검증 | 담당 workitem |
| --- | --- | --- | --- |
| AC-01 | 선행: SPEC-001-WI-01. ALT/HDG 부분 지시, null 사유, UTC 촬영/처리 시각, source, 지시 연결, 채널 상태, 필드별 점수·품질·근거 참조를 버전 계약과 정상/실패 예제로 정의한다. 부분 변경 후 항목별 목표값·원본 지시 연결을 구분한다 | 스키마 예제 검증; 기존 필수 Observation과 확장 호환성 대조 | [SPEC-002-WI-01](#wi-01) |
| AC-02 | 선행: SPEC-002-WI-01. 최초 입력·수정 입력·health를 수신하고 stale/다른 지시/중복/역순 입력이 잘못된 VERIFIED 또는 RESOLVED를 만들지 않는다 | 현재 API 회귀와 새 계약·연결·freshness 경계 테스트; DB 변경은 재현 가능한 마이그레이션 | [SPEC-002-WI-02](#wi-02) |
| AC-03 | 선행: SPEC-002-WI-02. mock 생산자와 backend가 정상/부분 지시/미인식/장애/새 지시/재검증 예제를 동일한 의미로 처리한다 | 버전·단위·null·타임스탬프 계약 통합; 실제 입력 성공은 별도 기록 | [SPEC-002-WI-03](#wi-03) |

## Work items

진행 상태는 [TODO](todo.md)에서만 관리합니다. 상세 범위와 결과 기록은 각 workitem 파일에 있습니다. 기존 앵커는 외부 링크 호환을 위해 유지합니다.

<a id="wi-01"></a>

### [SPEC-002-WI-01: 공통 관측·품질·근거 계약 정의](002-observation-contracts/workitem/wi-01.md)

<a id="wi-02"></a>

### [SPEC-002-WI-02: 백엔드 수신·지시 연결과 중복/지연 처리](002-observation-contracts/workitem/wi-02.md)

<a id="wi-03"></a>

### [SPEC-002-WI-03: 생산자·소비자 계약 통합 검증](002-observation-contracts/workitem/wi-03.md)

## 변경 기록

- v6 · 2026-10-18: WI-02 수신 API·SQLite 추가 마이그레이션·원자 저장·중복/충돌·시도/지시 연결·stale/역순/장애 복구 구현. 구간 등록은 비동기 STT 실행과 구분해201을 반환. 정책은 명시 설정·비행별 고정, 미설정/불확실 입력과 최종 비교 미구현은 UNVERIFIED로 유지.

- v5 · 2026-10-17: WI-01 공통 계약 실행 산출물 확정. 원본 시각 미상은 null+time_basis/사유로 보존하고 품질을 필드별로 명시. source별 shape·시도/지시 연결·부분 변경 목표·health·접수/오류 DTO, JSON Schema 6종 및 예제 검증. 기존 v1 route 유지; v2 수신·DB 마이그레이션은 WI-02.

아래 과거 버전의 ‘미정’은 당시 기록이다. 현재 실행 기준은 본문의 최신 계약·처리 기준이며 과거 질문을 다시 사용자에게 묻지 않는다.

- v4 · 2026-10-17: 누적 사용자 답변과 timeCapsule 상세화 기준에 따라 입력·출력, 처리 순서, 실패·복구, WI 실행 계획·인수 사례를 보강. 사용자 결정과 기술안을 분리하며 기존 구현 상태·검증 이력을 유지.

- v3 · 2026-10-17: timeCapsule의 계약·흐름·실패·인수 사례 수준을 참고해 확장 계약 기술안 추가. 중복·충돌·늦은 결과 경계 명시. WI-01/02/03에 적용하며 API 구현과 검증 완료를 뜻하지 않음.

- v2 · 2026-10-17: D-007-04 부분 변경 요구에 따른 항목별 지시 출처 보존 계약 추가.

- v1 · 2026-10-10: 사용자 제공 기획·Priority·자문과 현재 코드로 최초 작업 초안 작성. 문서 작성 권한과 기능 구현 권한은 구분한다.

- 2026-10-14: 기존 WI ID·범위·검증 기록을 보존해 각 스펙의 workitem/ 개별 파일로 이동. 요구사항 변경 없이 구조만 분리.
