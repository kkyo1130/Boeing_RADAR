# 공통 관측 수신 API — SPEC-002-WI-02

`radar-observation/1`은 `/api/v1`에서 수신한다. 요청 형식은 [공통 계약](observation-v1.md)과 동일하다. 기존 `/api/flights`·`/api/clearances`는 Mock 전용 경로로 유지한다. 기존 DTO와 이 계약의 지시 ID·저장소를 혼용하지 않는다.

## 호출 순서

1. 기존 `POST /api/flights/start`로 비행을 시작한다.
2. `POST /api/v1/flights/{flight_id}/clearances`로 지시 ID를 예약한다. body는 없다. 응답은 clearance_id, flight_id, created_at, active, status, reasons, observations다. 같은 비행의 이전 v1 지시는 즉시 비활성화된다. 기존 legacy 지시는 영향받지 않는다.
3. 예약한 ID와 실제 비행 ID를 포함하여 `POST /api/v1/observations`에 ATC, READBACK, COCKPIT 순서로 보낸다. ATC 요청 필드가 null이면 그 필드는 비요청이며 객체 내 value=null이면 판독 실패다.
4. 수정 시 새 event_id/observation_id/sample_id와 intent=correction, 해당 source의 최신 supersedes_observation_id를 보낸다. 수정 ATC가 수신되면 이전 Readback/Cockpit을 모두 무효화하므로 새 입력을 initial로 제출한다.
5. `GET /api/v1/clearances/{clearance_id}`로 원본·사유·시각을 조회한다.
6. `GET /api/v1/flights/{flight_id}/observation-events`로 수신 이력을 조회한다. 기존 Safety Trace endpoint에는 이 v1 이력이 합쳐지지 않는다. 통합 Trace/Incident/판정은 SPEC-005/007/008의 후속 범위다.

## 수신 응답과 실패

관측 POST 응답은 event_id, accepted, replayed, received_at, reasons다. accepted는 **시간·순서·연결 검사를 통과해 저장된 관측**이라는 뜻이며 읽은 값의 정확성 또는 정상 판정이 아니다. null·낮은 품질도 정보를 잃지 않고 보존한다. 서버는 현재 모든 v1 지시를 UNVERIFIED와 validation_pending 사유로 반환하며 VERIFIED/RESOLVED를 생성하지 않는다. 3상태 비교와 규칙 검증은 SPEC-005에서 구현한다.

| 조건 | 동작 |
| --- | --- |
| 같은 event_id·같은 정규화된 내용 재시도 | 기존 receipt 재생(replayed=true), 이력·포인터 추가 없음 |
| 같은 event_id에 다른 내용, 관측 ID 재사용 | 409 |
| 같은 비행·채널의 원본 sample_id 재사용 | 409. 같은 원본을 재처리해 수정 근거로 쓰지 않음 |
| 없는 flight/clearance | 404 |
| 다른 비행 지시, 비활성 지시, 비행 종료, 순서/수정 대상 충돌 | 409 |
| 구조·단위·UTC·null 사유·근거 참조 위반 | 422 |
| stale / 시각 미상 / 지시 예약 이전 촬영 / 미래 시각 / 역순 | 200 accepted=false, 이유와 입력 전체를 이력에 저장, 최신 관측 교체 안 함 |

ID 재시도는 원래 수신 당시의 결과를 반환한다. 시간이 지난 뒤 accepted=true receipt를 재생해도 새 정상 판정이나 새 관측이 되지 않는다. GET은 조회 시각 기준으로 다시 stale을 표시한다.

## 시각·health 정책

`RADAR_OBSERVATION_MAX_AGE_SECONDS`는 유한한 양수 설정이며 기본값은 **모의 테스트용 30초**다. Q-04의 팀 인수 기준이나 검증된 안전 임계값이 아니다. age가 설정값을 초과하면 stale이며 정확히 같은 값이면 허용한다. 미래 촬영/처리는 허용하지 않고, unknown 캡처 시각은 수신 이력만 보존한다.

관측은 예약 시각 이후, Readback/Cockpit은 최신 ATC 촬영 시각 이후여야 한다. correction은 같은 source의 최신 관측을 참조하고 그 촬영 시각보다 엄격히 새로워야 한다. 지시 생성 전에 확보한 샘플을 새 지시에 재사용하지 않는다.

채널의 accepted 이벤트 processed_at을 watermark로 사용해 역순을 거부한다. 거부된 미래 시각 이벤트는 watermark를 오염시키지 않는다. 서버 신뢰 시각과 생산자 UTC 동기화가 필요하다. 임의 시각을 처리 시각으로 보정하지 않는다.

health는 sample/observation/fields 없이 전송하며 지시 미연결이면 clearance_id=null이다. processed_at으로 age·역순을 검사한다. 같은 비행/channel_id의 accepted 장애 health는 해당 채널을 사용한 지시 조회의 보류 사유에 반영한다. 새 available health만으로 정상/해결을 만들지 않는다. health의 source는 입력 채널에 지정된 역할이며 역할을 모르는 발화의 최종 구조화는 후속 음성 작업에서 다룬다.

## DB와 실행

기존 테이블을 바꾸지 않고 `contract_clearances`와 `contract_events`를 추가한다. event에는 수신 시각·원본·accepted/reasons를 저장한다. 최신 포인터와 이력은 동일 트랜잭션이다. SQLite에서는 BEGIN IMMEDIATE로 수신·예약의 읽기/검사/쓰기를 직렬화하고 ID/sample DB 제약으로 중복을 막는다. 다른 DB에는 flight 행 잠금을 적용하지만 이번 검증은 SQLite만 수행한다. legacy API의 병렬 변경 정책까지 확장하지 않는다.

기존 DB에 대한 명시적·반복 실행 가능한 추가 마이그레이션은 backend에서 실행한다. 기본 DB는 기존 설정을 따른다. 앱 시작 시 create_all도 신규 테이블을 만든다.

```sh
python -m app.migrate_contract_storage
python -m pytest -q
uvicorn app.main:app --reload
```

마이그레이션은 기존 비행/지시/Trace를 변경하지 않는다. 삭제 downgrade를 제공하지 않는다. 실카메라·마이크·SDR 생산자 어댑터와 실제 HTTP 장비 입력 검증은 수행하지 않았다. 예제의 고정 시각·가짜 ID를 운영 요청에 그대로 사용하지 않고 예약한 ID와 원본의 실제 관측 시각을 제공한다.
