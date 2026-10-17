# 공통 관측 v2 수신 API

SPEC-002-WI-02의 실행 계약이다. [WI-01 DTO·구조 계약](observation-v2.md)을 기존 Mock API와 분리된 `/api/v2`에 연결한다. 입력 저장·문맥 검증·현재 항목/목표 연결을 구현하며 최종 숫자 비교(NORMAL/MISMATCH)·알림·Incident 해결은 SPEC-005/006/007의 후속 범위다. v2 state는 항상 UNVERIFIED로 표시해 수신 성공을 전체 정상으로 만들지 않는다.

## 설정과 설치

Backend의 기존 requirements로 설치한다. 개발자가 `RADAR_V2_CONFIG`에 [설정 예제](receiving-v2.example.json)를 복사한 파일 경로를 지정한다. callsigns는 대표 호출부호→등록 alias_key→정확한 허용 발화 문자열의 사전이다. 별칭은 대소문자·연속 공백만 정규화하고 모델의 유사 발음 추정으로 추가하지 않는다. 같은 정규화 발화가 둘 이상의 별칭에 중복되면 설정을 거부한다. 미등록 호출부호로 시작할 수 없다.

`freshness=null`은 정책 미설정이며 입력은 이력으로 수신해도 목표·현재값을 적용하지 않는다. 운용 기본 임계값을 임의로 만들지 않는다. 설정할 때는 아래 세 항목을 모두 명시한다.

| 항목 | 형식·적용 |
| --- | --- |
| max_age_seconds | 양수 유한 숫자. 관측부터 서버 수신/조회까지 허용 나이 |
| max_future_skew_seconds | 0 이상 유한 숫자. 미래 원본·처리 시각 및 아직 끝나지 않은 구간 거부 기준 |
| minimum_model_score | 0~1 유한 숫자 또는 null. null은 점수 문턱 비활성화지만 입력 품질 검사는 유지 |

테스트의 10초·0.2초·0.5점은 가상 시계 fixture의 수치다. 실장비에 검증된 기준이 아니다. 설정·등록 목록은 비행 생성 때 snapshot으로 고정한다. 파일을 나중에 수정해 이미 시작한 비행의 허용 범위를 바꾸지 않는다. 모든 비교 항목과 호출부호는 input_quality=SUFFICIENT여야 한다. 모델 점수는 정확도/확률로 표시하지 않는다.

실행 위치는 backend다. 일반 서버 명령은 `uvicorn app.main:app --reload`이며 시작 시 추가 테이블 migration을 수행한다. 기존 DB를 별도로 준비하려면 다음 명령을 사용한다.

```sh
python -m app.migrate_observation_v2 --database-url sqlite:///./radar.db
```

마이그레이션은 기존 flights/clearances/safety_events의 컬럼·데이터를 변경하지 않고 v2 context/instruction/segment/input/trace/migration 테이블만 추가한다. 같은 DB에서 다시 실행해도 migration 버전 행은 한 건이다. 검증된 DB는 SQLite이며 다른 DB의 locking/마이그레이션 동작은 별도 검증이 필요하다.

## endpoint와 응답

| 메서드·경로 | 입력·결과 |
| --- | --- |
| POST `/api/v2/flights` | `{callsign}`. 등록/설정 검사 후 201 세션과 고정 정책 snapshot 반환 |
| POST `/api/v2/flights/{flight_id}/end` | 200 종료. 이후 관측·health·구간 등록/취소·중복 종료409 |
| POST `/api/v2/flights/{flight_id}/speech-segments` | SpeechSegmentV2. 201 등록 또는 동일 재전송200. ATC 구간에는 서버 instruction_id를 예약해 반환 |
| POST `/api/v2/flights/{flight_id}/speech-segments/{segment_id}/cancel` | `{reason}`. 현재 시도 취소200. 이미 채택된 ATC 지시는 취소409 |
| POST `/api/v2/flights/{flight_id}/observations` | ObservationV2. 201 신규 접수, 동일 ID·내용200 DUPLICATE, ID 내용 충돌409 |
| POST `/api/v2/flights/{flight_id}/health-events` | HealthEventV2. 201 접수 또는 동일 이벤트200 |
| GET `/api/v2/flights/{flight_id}/state` | 항목별 목표·출처, 이번 복창 요구, 채널, 현재 관측/사유. 최종 result=UNVERIFIED |
| GET `/api/v2/flights/{flight_id}/inputs?limit=100` | 최신순 입력·원본 payload·applied·사유·접수 이벤트 참조. 최대1000 |
| GET `/api/v2/flights/{flight_id}/safety-trace?after=0&limit=100` | 이벤트 순서·시각·revision·원본/변경 snapshot. sequence 오름차순, 최대1000 |

404/409/422는 [ContractErrorV2](schemas/contract-error-v2.schema.json) envelope다. 기존 `/api`의 422 detail 형식은 유지한다. 신규 관측/health의 응답은 [IngestionReceiptV2](schemas/ingestion-receipt-v2.schema.json)이며 `applied`나 NORMAL 필드를 넣지 않는다. 구체 반영 여부·보류 사유는 inputs/state/trace에서 확인한다.

이 단계의 speech-segments는 **이미 수음한 구간의 등록**이다. STT 작업을 실행하거나 작업 큐에 넣지 않아 202 작업 완료처럼 표시하지 않고 201을 반환한다. 실제 STT 접수·작업 상태는 SPEC-004에서 추가한다. 완전한 운영 UI·리포트·음성 재생 API는 이번에 등록하지 않는다.

## 처리와 연결

1. URL/body의 flight_id·DTO 구조·버전을 검증하고 활성 v2 비행을 확인한다. 기존 v1 세션은 자동 변환하지 않는다.
2. 입력 종류와 input_id의 유일성을 확인한다. 같은 내용 재전송은 기존 event_id/received_at을 반환하고 상태 revision·Trace를 추가하지 않는다. 다른 내용·비행은409다.
3. 음성은 먼저 구간을 등록해야 한다. ATC input/segment/attempt/role을 함께 검사하고 READBACK instruction_id는 예약된 ATC 지시와 정확히 일치해야 한다. 불일치를 다른 지시로 재연결하지 않는다.
4. 취소·불완전·이전 Pilot 시도·더 이전 ATC 결과는 이력으로만 보존한다. 같은 source의 원본 frame/segment를 새 observation_id로 다시 보내도 적용하지 않는다.
5. UTC 원본 시각·정책·채널·품질·등록 호출부호·원본 목표 버전을 검사한다. unknown/stale/future는 보류한다. UNKNOWN 명시 범위와 추출 실패를 부분 지시 성공으로 채택하지 않는다.
6. 적격 ATC만 명시한 목표 항목을 바꾸고 지시/관측 출처를 보존한다. ALT B/4000과 HDG A/270은 별도 출처다. 목표 갱신만으로 복창/설정 일치가 되지 않는다.
7. 새 목표 채택 전에 도착한 동일 ATC의 Pilot 결과는 ATC_NOT_ADOPTED로 대기하고 해당 ATC가 채택되면 같은 트랜잭션에서 다시 문맥을 확인한다. 완료 순서로 연결을 바꾸거나 재발화를 강제하지 않는다.
8. 적용 가능한 현재 값과 보류 이유·원본 입력·Trace snapshot을 한 트랜잭션으로 저장한다. SQLite는 BEGIN IMMEDIATE로 수신·종료 writer를 직렬화하고, 실패하면 모두 rollback한다.

Pilot 구간 시작은 해당 ATC 구간 종료보다 이르면 안 된다. 같은 입력의 Pilot 재시도는 새 segment/attempt를 요구하고 구간 시각이 역순이면409다. 새 ATC 재시도는 새 atc_input_id를 요구한다. ATC payload의 observed_at은 구간 시작과 일치해야 하고, 미상은 그대로 보류한다.

## 시간·장애·수정 안전성

- 카메라 관측은 해당 항목 목표가 채택된 시각보다 **뒤에** 촬영되고, 그 목표 revision을 알고 있어야 현재 값으로 적용한다. 변경되지 않은 항목의 출처·유효 관측은 유지한다. 서버의 현재 revision보다 큰 target_revision은 409 CONTEXT_MISMATCH로 거부하며 상태·입력·Trace를 변경하지 않는다.
- 더 오래된 결과는 새로운 현재값을 덮어쓰지 않는다. 미상 시각·최신 저품질·판독 불가는 현재값을 null로 표시하고 이유를 남긴다.
- GET state에서도 시간 경과를 검사해 새 이벤트가 없더라도 expired 현재값을 null/STALE_OBSERVATION으로 돌려준다. 이력의 원본 숫자는 유지한다.
- 끊김 health와 복구 AVAILABLE 모두 기존 현재값을 지운다. health보다 뒤의 새 적격 관측을 받기 전 이전 숫자를 현재값으로 재사용하지 않는다. 오래된 health는 채널 상태를 되돌리지 못한다.
- 카메라 끊김은 CAMERA, 마이크/음성 API 장애는 해당 speech 채널로 구분한다. 명시된 SPEECH_API 장애가 남아 있으면 음성 추출 결과로 새 목표를 채택하지 않는다.
- 잘못된·취소된·다른 시도 결과는 같은 원본을 다시 처리해 정상으로 바꾸지 않는다. 입력접수201·검사PASS·target 채택 모두 최종 정상 판정이 아니다.

## 기존 API·이력과 인수인계

v2 숫자/health payload는 새 v2 Trace 테이블에 보존한다. 기존 SafetyEventResponse의 Observation·enum을 깨지 않도록 legacy trace에는 기존 형태의 비행 시작/종료만 기록한다. UI가 v2 입력을 조사할 때는 v2 safety-trace를 사용한다. 전체 비행 리포트·통합 집계는 SPEC-008에서 연결한다. legacy VERIFIED 값을 v2의 현재 판정으로 읽지 않는다.

WI-03은 mock 생산자와 이 API를 연결해 정상/부분 지시/미인식/장애/새 지시/수정 관측 계약을 통합 검증한다. SPEC-005는 현재값의 숫자 비교·규칙·전체 상태를, SPEC-007은 Incident 수정 해결을 구현한다. 이 WI는 새 관측 수신 경로가 거짓 VERIFIED/RESOLVED를 만들지 않는 것을 검증하며 실제 기기 성능을 주장하지 않는다.
