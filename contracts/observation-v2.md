# RADAR 공통 관측 계약 v2

SPEC-002-WI-01의 산출물이다. DTO와 JSON Schema·예제를 검증한 공통 계약이며, `/api/v2` 서버 수신·DB 저장·freshness 판정은 WI-02에서 구현한다. 현재 `/api`는 기존 ObservationInput 계약을 유지한다. 외부 API·실카메라 연동 성공을 뜻하지 않는다.

## 원본과 재현

- 의미·흐름: [SPEC-002](../docs/spec/002-observation-contracts.md).
- 실행 가능한 타입·교차 검증 원본: [observation_v2.py](../backend/app/schemas/observation_v2.py).
- 언어 독립 구조 스키마: [schemas/](schemas/). Draft 2020-12, `$id=urn:radar:contracts:<이름>`.
- 입력·응답·실패 예제: [manifest.json](examples/v2/manifest.json). 원본 미디어를 포함하지 않는 합성 계약 fixture다.
- 검사·스키마 생성: [check_v2.py](check_v2.py). DTO에서 생성하며 JSON을 따로 손으로 수정하지 않는다.

저장소 루트에서 다음을 실행한다. backend 의존성에 Pydantic·pytest·jsonschema가 필요하다.

```sh
backend/.venv/bin/python contracts/check_v2.py --write
backend/.venv/bin/python contracts/check_v2.py
```

Backend 회귀는 `backend/`에서 `.venv/bin/python -m pytest -q`로 실행한다. `--write`는 스키마를 갱신하고 기본 검사는 파일이 DTO와 일치하는지 및 모든 예제의 기대 결과를 확인한다. 스키마는 v2 라우터에 자동 등록되지 않는다.

## 메시지 종류와 책임

| 스키마 | 방향·용도 | 필수 구분 |
| --- | --- | --- |
| [observation-v2](schemas/observation-v2.schema.json) | Vision/음성 추출 → Backend | `source=COCKPIT/ATC/READBACK` 판별 union. source별 필드 외 추가 입력 금지 |
| [health-event-v2](schemas/health-event-v2.schema.json) | 장치/어댑터 → Backend | 숫자 없이 채널 상태 전달. CAMERA/MICROPHONE/SPEECH_API |
| [speech-segment-v2](schemas/speech-segment-v2.schema.json) | 수음 제어 → 음성 처리 | 구간·ATC 입력·시도·역할·원본 참조·완료 여부 |
| [target-snapshot-v2](schemas/target-snapshot-v2.schema.json) | Backend → 생산자/UI | ALT/HDG별 목표·원본 지시와 이번 지시의 복창 요구 |
| [ingestion-receipt-v2](schemas/ingestion-receipt-v2.schema.json) | Backend → 생산자 | 접수·동일 재전송 확인. 정상/해결 판정 필드 없음 |
| [contract-error-v2](schemas/contract-error-v2.schema.json) | Backend → 생산자 | 코드·사유·입력 ID·오류 위치. 실패를 가짜 숫자로 반환하지 않음 |

세션 시작/종료, 비동기 작업 상태, 완전한 운영 UI snapshot·리포트·음성 재생 이벤트의 도메인별 DTO는 해당 WI가 위 공통 타입을 참조해 추가한다. 본 WI는 관측/구간/health/목표/접수/오류 경계를 검증한다.

## 공통 envelope

| 필드 | 형식·조건 |
| --- | --- |
| `schema_version` | 문자열 `"2"`만 허용. 숫자2나 로컬 Vision 버전은 거부 |
| `observation_id`, `flight_id` | 영문/숫자로 시작, 영문/숫자/점/밑줄/콜론/하이픈, 1~128자. 재전송 시 같은 observation ID와 같은 내용 유지 |
| `observed_at` | 원본 관측 시각 UTC 문자열 또는 명시적 null. 필드를 생략하지 않음 |
| `processed_at` | 처리 완료 UTC 문자열. `observed_at`이 있으면 그보다 이르지 않음 |
| `time_basis` | CAPTURED: 알려진 촬영/수음 시각, HOST_RECEIVE: 호스트 프레임 수신 시각, UNKNOWN: 촬영 시각 미상 |
| `time_reason` | UNKNOWN일 때 null 시각과 함께 비어 있지 않은 사유. 알려진 시각에는 null |
| `target_revision` | 생산자가 알고 있던 서버 목표 버전, 0 이상 정수. 최신성이나 지시 소유권을 보장하지 않음 |
| `channel_health` | AVAILABLE/null 사유 또는 DEGRADED·DISCONNECTED/명시적 사유 |
| `evidence_refs` | 선택 원본 참조 목록. 빈 목록이면 `evidence_unavailable_reason` 필수; 참조가 있으면 사유는 null |

모든 UTC 문자열은 `YYYY-MM-DDTHH:MM:SS[.ffffff]Z`다. 실제 달력에 존재하는 날짜와 시각만 허용한다. 오프셋 시각은 생산자가 UTC로 변환하며 시간대 없는 문자열이나 Unix 숫자를 보내지 않는다. `processed_at`·수신 시각·파일 수정 시각을 촬영 시각으로 바꾸지 않는다. HOST_RECEIVE도 물리적 촬영 시각을 증명하지 않으며 서버가 적용 환경·시계 기준을 검사한다.

`flight_id`는 body에도 명시한다. WI-02는 URL 비행 ID와 일치하는지 검사해 다른 비행으로 들어오는 재전송을 거부한다. 신뢰할 수 없는 미래 시각·역순·stale·취소된 시도 여부는 서버 수신 시점과 저장 상태로 검사한다. 현재 시각 없이 검증하는 DTO는 오래된 입력도 이력 기록용으로 표현하며 수신 성공을 NORMAL로 바꾸지 않는다.

## 항목값·품질·근거

`fields.ALT`: `unit="ft"`, value는 0 이상 정수 또는 null. `fields.HDG`: `unit="deg"`, value는 0~359 정수 또는 null. 숫자 문자열·boolean·소수는 수치로 변환하지 않는다. FL→feet는 명시적 원문 단위를 확인한 생산자가 변환하고 raw_text에 원문을 남긴다. HDG360을0으로 보정하지 않는다.

각 항목은 다음 상태를 가진다.

| validity | value | reason |
| --- | --- | --- |
| VALID | 범위 내 정수 | null |
| UNREADABLE | null | 비어 있지 않은 판독 실패 사유 |
| INVALID | null | 범위/형식 등 거부 사유 |

`raw_text`는 원문 또는 null이다. 거부된 원문 숫자는 raw_text에 남기며 current value에는 넣지 않는다. 원인 코드는 `blank_roi`, `no_text`, `unstable_reading`, `stale_frame` 등 생산자 코드이며 확실하지 않은 가림 원인을 임의로 `occluded`로 정하지 않는다. 이 상태는 입력값 유효성이고 최종 NORMAL/MISMATCH/UNVERIFIED가 아니다.

품질은 **항목마다** `quality`에 명시한다.

- `model_score`: 유한한0~1 숫자 또는 null. 점수 없음이 정확도100%를 뜻하지 않음.
- `input_quality`: SUFFICIENT/INSUFFICIENT/UNKNOWN. 점수와 입력 품질은 다른 정보다.
- `reason`: 점수가 없거나 품질이 SUFFICIENT가 아닐 때 필수. 단일 contrast 측정값만으로 일반 영상 품질을 SUFFICIENT로 주장하지 않음.
- `score_calibrated`, `calibration_ref`: 보정 여부와 검증 자료 참조를 구분. true이면 점수와 참조가 모두 필요하고 false이면 참조는 null. 보정 여부만으로 운용 정확도를 보장하지 않음.

근거 참조는 `evidence_id`, `kind`, `ref`, `field`, `roi`를 가진다. ROI는 필드명과 `[left, top, right, bottom]` 비음수 정수 좌표가 필요하며 폭·높이는 양수다. 전체 FRAME에는 ROI 좌표를 넣지 않는다. 참조 ID는 메시지 안에서 중복 금지다. `ref`는 식별/조회용 참조이며 서버가 임의 로컬 경로나 외부 URL을 자동으로 열라는 명령이 아니다. 실제 저장·접근·삭제는 수신 구현에서 정의한다. 참조 문자열 검증은 파일 존재 검증이 아니다.

R-02에 따라 종료 리포트는 숫자·상태·시각으로 완성하며 미디어 참조가 없어도 조회 가능해야 한다.

## COCKPIT과 음성의 차이

COCKPIT은 `frame_id`, ALT·HDG 두 항목을 항상 포함한다. 한 항목 판독 불가는 해당 value만 null로 남긴다. 카메라 DISCONNECTED 상태에 현재 숫자값을 함께 보내지 않는다. 순수 끊김 통지는 숫자가 없는 HealthEventV2를 사용한다. COCKPIT 근거는 FRAME/ROI다.

ATC/READBACK은 `segment_id`, `atc_input_id`, `attempt_id`, `transcript`, `transcript_reason`, `callsign`, `mention_status`, `mentioned_fields`, `instruction_check`를 가진다. READBACK에는 비교 대상 `instruction_id`도 필수다.

- `mentioned_fields`는 이번 발화에서 명시된 항목으로 중복이 없어야 하며 fields의 키와 일치한다.
- 생략된 항목은 키 자체를 넣지 않는다. 말했지만 추출 실패한 항목은 키를 남기고 value=null+사유로 보낸다.
- 명시 여부를 확실히 판별할 수 없으면 `mention_status=UNKNOWN`, `instruction_check=NEEDS_REVIEW`. 일부 추출 성공값으로 부분 지시를 자동 채택하지 않는다.
- STT가 전부 실패하면 transcript=null+사유, UNKNOWN·빈 mentioned_fields/fields와 호출부호 판독 실패를 함께 표현할 수 있다.
- PASS는 구조화 검사 통과이며 목표 일치나 운항 정상 판정이 아니다. PASS는 명시 범위·호출부호·추출값이 유효하고 입력 채널이 AVAILABLE일 때만 허용한다. 누락 복창의 완전성은 서버가 원본 지시와 추가 대조한다.
- 호출부호의 VALID는 raw_text·정규값·alias_key를 요구한다. 등록 목록과 별칭이 실제 대응하는지 및 세션 대상인지 서버가 별도 확인한다. 판독 불가에는 value/alias_key를 null로 남기며 세션값으로 채우지 않는다.
- 음성 근거 종류는 AUDIO/TRANSCRIPT다. 역할은 모델 추정이 아니라 수음 제어 구간의 역할 근거를 사용한다.

## 부분 변경과 수정 연결

[targets-partial.json](examples/v2/targets-partial.json)은 A의 ALT3000/HDG270 이후 B의 ALT4000을 반영한다. ALT 출처는 B, HDG 출처는 A로 남고 `readback_required.fields=["ALT"]`다. DTO는 복창 요구 범위가 새 지시의 목표 필드와 맞는지 검사한다. 누적 목표 전체를 B의 복창 요구로 합치지 않는다.

새 수정 관측은 새 observation/frame/segment ID와 원본 시각을 갖는다. `atc_input_id`는 처리 완료 순서가 아닌 수음 시점의 ATC 입력을 연결하고 `attempt_id`는 재입력을 구분한다. ID만 새로 만든 오래된 프레임, 다른 ATC의 Pilot 결과, 종료·취소된 시도의 늦은 응답은 WI-02가 서버 상태와 대조해 배제한다. 이 DTO만으로 RESOLVED 상태를 만들지 않는다.

SpeechSegmentV2는 ATC→ATC_PLAYBACK, PILOT→PILOT_PTT를 강제한다. 종료 시각은 시작보다 뒤여야 한다. 불완전 녹음은 중단 사유가 필수이며 이력으로만 보존한다. 실제 음성 처리는 complete=true와 audio_ref가 있는 구간에서만 시작한다. 장치/파일 접근 가능 여부는 음성 수음 WI에서 검증한다.

## 접수·오류와 후속 수신 구현

| 상황 | HTTP 계약 | 처리 의미 |
| --- | --- | --- |
| 새 관측/health | 201 + IngestionReceiptV2 | 기록 접수; 판정 정상·해결을 의미하지 않음 |
| 동일 ID·동일 내용 재전송 | 200 + DUPLICATE | 기존 접수 결과 참조, 이벤트 중복 생성 금지 |
| 동일 ID·다른 내용 | 409 ID_CONTENT_CONFLICT | 덮어쓰기 금지 |
| 형식·단위·버전 오류 | 422 INVALID_PAYLOAD/UNSUPPORTED_VERSION | 유효 관측으로 저장하지 않음 |
| 없는 비행·지시 | 404 NOT_FOUND | 임의 세션 생성 금지 |
| 비행 ID·시도·지시 연결 불일치 | 409 CONTEXT_MISMATCH/INVALID_SEQUENCE | 다른 입력으로 재연결 금지 |
| 종료 비행 입력 | 409 FLIGHT_ENDED | 현재 상태/종료 리포트 갱신 금지 |

404·409·422 응답의 구체 envelope는 ContractErrorV2다. 알 수 없는 schema_version은 모델 검증 전에 수신 경계에서 구분할 수 있다. 202 비동기 작업 접수는 최종 관측 수신과 별도다. endpoint 경로 계획은 SPEC-002를 따르며 이 표는 아직 실행 API가 아니다.

## 기존 구현과 호환성

| 기존 입력 | v2로 옮길 때 필요한 일 |
| --- | --- |
| 현재 backend ObservationInput | `altitude/heading/confidence` 필수, null/부분 지시 미지원. v2 DTO를 같은 endpoint에 보내지 않음. v1의 생략 시각 서버 대체를 실제 관측 시각으로 해석하지 않음 |
| `vision-poc/1`, `vision-poc/2` | `fields.altitude/heading`→ALT/HDG, feet/degrees→ft/deg. 필드별 model_score·reason·ROI·원문을 각각 옮기고 입력 품질은 별도 평가. captured_at=null이면 UNKNOWN 유지 |
| `vision-stream/1` | 이벤트 안 observation과 health를 분리. host_receive는 HOST_RECEIVE, 파일은 UNKNOWN. 로컬 available/degraded/unavailable의 실제 원인을 보고 AVAILABLE/DEGRADED/DISCONNECTED로 매핑하며 unavailable을 모두 연결 끊김으로 단정하지 않음 |
| 로컬 frame UUID·frame_sequence | 재실행/재전송 identity와 구분. 공통 observation ID는 같은 요청 재전송 동안 유지. 원본 시각을 보존해 오래된 파일이 새 관측으로 둔갑하지 않게 함 |
| 선택 speed 필드 | 기존 로컬 Vision 관측에 유지. 이번 ALT/HDG 공통 서버 계약에 자동 혼입하거나 속도 비교를 추가하지 않음 |

기존 Vision 어댑터의 전송 구현은 SPEC-003-WI-04, 실제 수신·중복/지연/DB 마이그레이션은 SPEC-002-WI-02, 생산자/소비자 실통합은 WI-03에서 수행한다. v1↔v2 자동 변환·임의 단일 confidence 합성·null→0 변환을 제공하지 않는다.

## Schema와 DTO의 검증 경계

JSON Schema는 타입·범위·단위·source별 shape·VALID/null 조건을 검증한다. Pydantic DTO는 추가로 관측/처리 시각 순서, 명시 필드 집합 일치, 호출부호 상태, 품질·보정 참조, 근거·ROI 관계, 부분 지시 출처와 복창 범위를 검사한다. JSON Schema만 통과한 데이터를 수신 완료로 처리하지 말고 DTO의 교차 검증 또는 동일한 규칙의 소비자 검사를 적용한다.

manifest의 `schema_valid`와 `valid`는 각각 JSON Schema·DTO 기대 결과다. `invalid-mentions.json`, `invalid-target-scope.json`은 구조는 유효하지만 교차 검증에서 거부하는 예다. 어느 검사도 실제 현재 시각·등록 목록·저장된 지시·이전 시도를 조회하지 않으며 최종 판단은 Backend 서비스가 수행한다.
