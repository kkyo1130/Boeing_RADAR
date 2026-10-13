# RADAR 공통 관측 계약 — radar-observation/1

SPEC-002-WI-01의 버전 계약이다. 서버·Vision·통신이 연결할 목표 형식이며 **현재 API가 이 형식을 수신한다는 뜻은 아니다**. Python 계약 원본은 [ObservationContract](../backend/app/schemas/observation_contract.py), 배포용 구조 스키마는 [JSON Schema](schemas/observation-v1.schema.json)다. Pydantic의 교차 필드 검사도 계약의 일부이므로 JSON Schema 검사만으로 유효성을 확정하지 않는다.

## 이벤트와 연결

모든 필드는 명시적으로 포함한다. 추가 필드는 거부한다. 아래 nullable 항목만 null을 허용한다. ID는 공백 없는 비어 있지 않은 문자열이다.

| 필드 | 타입·의미 |
| --- | --- |
| schema_version | 고정 문자열 `radar-observation/1` |
| event_type | `observation` 또는 `health` |
| event_id | 이벤트 고유 ID. 네트워크 재시도는 같은 ID·같은 내용을 유지 |
| observation_id | 관측 ID. observation에서 필수, health에서 null |
| flight_id / clearance_id | 비행/지시 연결 ID. observation은 둘 다 필수, health는 지시 미연결이면 clearance_id=null |
| source | `ATC`, `READBACK`, `COCKPIT`. ATC/Pilot 역할을 발화 순서만으로 확정하지 않음 |
| channel_id | 입력 장치/수신 채널 ID. health도 같은 채널을 사용 |
| input_mode | camera / microphone / sdr / image_file / audio_file / video_file / fixture. 실제 장치와 파일 검증 구분 |
| sample_id | 프레임 또는 음성 구간 ID. observation 필수, health는 null. 같은 원본을 재처리하면 동일 sample_id를 유지 |
| captured_at | UTC ISO 8601 관측 시각 또는 null. 시간대 생략·비UTC·숫자 epoch 거부 |
| capture_time_basis | device / host_receive / provided / unknown. unknown일 때만 captured_at=null |
| processed_at | 필수 UTC ISO 8601 처리 완료 시각. 알려진 captured_at보다 빠를 수 없음 |
| health | status=available/degraded/unavailable, reason. available은 reason=null, 나머지는 사유 필수 |
| intent | observation은 initial/correction, health는 null |
| supersedes_observation_id | initial/health는 null. correction은 수정 대상의 서로 다른 기존 관측 ID |
| fields | observation은 ALT/HDG 필드 객체, health는 null |
| speech | ATC/READBACK 관측의 음성 문맥 객체. COCKPIT/health는 null |
| evidence | 근거 객체 배열. 근거 없음은 빈 배열, health는 반드시 빈 배열 |

최초 ATC도 지시 ID를 미리 할당받거나 서버가 예약한 ID를 사용한다. 기존 서버는 ATC 수신 시 지시를 생성하므로 이 연결 방식은 WI-02에서 구현한다. 역할 미확정 구간은 ATC/READBACK을 추정해서 전송하지 않고 해당 입력 채널의 degraded health와 사유로 전달한다.

관측 ID는 처리 결과, sample_id는 원본을 식별한다. 새로운 수정 관측에는 새 관측 ID뿐 아니라 **수정 이후의 새 원본**이 필요하다. 스키마만으로 원본 중복·지시 소유·freshness를 확인할 수 없으므로 WI-02/007에서 서버가 검사한다. 같은 입력의 재처리를 새 관측 근거로 사용하지 않는다.

host_receive는 호스트 수신 시각이며 센서 노출 시각을 증명하지 않는다. 파일은 원본 촬영 시각을 모르면 null/unknown으로 전달한다. 처리 시각·파일 수정 시각으로 대체하지 않는다. 오래된 입력과 unknown 시각의 최종 보류 정책은 WI-02/005에서 적용한다.

## 부분 지시·판독 불가·0의 구분

fields에는 altitude와 heading 키가 모두 필수다.

- 필드 객체가 null이면 해당 지시에서 요청하지 않은 항목이다. 서버는 ATC 요청 항목과 Readback/Cockpit 관측을 대조해 필요한 필드가 빠지지 않았는지 확인한다.
- 필드 객체의 value=null이면 요청된 항목을 읽지 못했다는 뜻이다. reason을 반드시 제공한다.
- value=0은 관측된 숫자다. 결측값으로 변환하지 않는다.

적어도 하나의 필드 객체가 필요하다. ALT는 0 이상의 엄격한 정수, unit=feet다. 입력 FL은 숫자×100으로 변환하고 raw_text에 원문을 남긴다. 운용 상한은 이 구조 계약에서 임의로 정하지 않는다. HDG는 엄격한 정수 0–359, unit=degrees다. 360을 자동으로 0으로 바꾸지 않는다. 문자열 숫자·boolean은 거부한다. 속도·QNH/Baro는 이 공통 비교 계약에 포함하지 않는다.

각 필드는 value, unit, reason, raw_text(string|null), model_score(number|null), score_calibrated, quality, evidence_ids를 포함한다. 값이 존재하면 reason=null, 값이 null이면 사유가 필수다. 모델 점수는 유한한 0–1이며 누락은 null이다. score_calibrated는 이 버전에서 false만 허용한다. 점수를 정확도나 검증된 확률로 표현하지 않는다.

quality는 status=acceptable/degraded/unknown과 reasons 배열이다. acceptable은 사유 없음, degraded/unknown은 사유 필수다. quality와 모델 점수는 독립적이다. degraded 상태에 숫자가 남아 있어도 정상 판정 허가를 뜻하지 않는다. 채널 unavailable 관측은 모든 요청 필드 value가 null이어야 한다.

사유는 소문자 snake_case 문자열이며 생산자 확장을 허용한다. 권장 사유: blank_roi, no_text, invalid_format, invalid_score, out_of_range, low_model_score, unstable_reading, occluded, blurred, stale_frame, capture_time_unknown, camera_disconnected, microphone_unavailable, overlapping_speech, ambiguous_role, callsign_missing. 알 수 없는 사유를 서버가 정상으로 해석해서는 안 된다.

## 음성 문맥·근거

speech는 transcript(string|null), callsign(string|null), callsign_reason(string|null), role_basis(string|null), conditions(string 배열), ordered_actions(string 배열)를 포함한다. 호출부호 누락은 null과 사유로 유지한다. 조건/순서는 원문 기반으로 보존하고 빈 배열을 문맥 검사 통과로 간주하지 않는다. 구조화와 결정론적 검사는 WI-004/005에서 수행한다.

근거 객체는 evidence_id, kind(image/audio), reference, availability(available/missing/unavailable), roi를 포함한다. reference는 저장소의 논리 참조(예: fixture:frame-1, evidence:audio-1)이며 로컬 개인 절대 경로나 임의 URL을 직접 열라는 명령이 아니다. 서버 저장·권한·조회·보존 정책은 WI-02/008에서 구현한다. 예제 fixture 참조는 설명용이며 실제 근거 파일의 존재를 보장하지 않는다.

roi는 image에만 허용하는 [left, top, right, bottom] 정수 픽셀 좌표 또는 null이다. EXIF 방향 적용 후 이미지의 좌상단 원점, 오른쪽/아래 경계 제외이며 비어 있는 사각형은 거부한다. 이미지 경계 검사는 원본을 보유한 생산자/서버 책임이다. evidence_id는 이벤트 내 중복 불가, 필드의 evidence_ids는 같은 이벤트 내 근거를 가리켜야 한다. 근거 누락은 reference를 숨기거나 가짜 경로로 채우지 않고 availability로 표시한다. 파일 검증과 실제 존재 확인은 별도다.

## 기존 구현과 호환성

| 구분 | 기존 서버 ObservationInput | 새 공통 계약 |
| --- | --- | --- |
| 필드 | altitude/heading/confidence 필수 | fields 아래 부분 지시/null/사유·필드별 점수 |
| 시각 | observed_at 생략 시 서버 시각, naive UTC 처리 | captured_at/basis와 processed_at 명시, UTC 필수 |
| 연결 | URL·서버 생성 clearance_id, endpoint별 source | flight_id/clearance_id/source/channel/sample/event ID 명시 |
| 품질·근거 | 미지원 | health/quality/evidence 별도 |
| 수정 | 기존 수정 endpoint | intent와 이전 관측 참조, freshness 서버 검사 필요 |

기존 DTO·OpenAPI·API endpoint는 유지한다. 새 JSON을 기존 endpoint에 직접 보내지 않는다. null을 0으로 채우거나 모델 점수를 단일 confidence로 합치는 자동 변환도 금지한다.

Vision의 vision-poc/1·2 및 vision-stream/1은 로컬 형식으로 유지한다. 후속 어댑터에서 서버 지시 ID, 안정적인 원본 ID, 시각 basis, 필드별 품질, 근거 참조를 매핑한다. Vision의 speed는 이 계약에서 제거하되 로컬 관측은 보존한다. 통신은 구간 ID·역할 근거·원본 참조를 전달한다. 최종 정상/불일치/보류는 서버만 결정한다.

## 예제와 검증

[예제 폴더](examples/observation-v1)는 normal, partial-atc(HDG=0), unreadable(ALT만 판독 불가), unknown-time, correction, health를 제공한다. 모든 예제는 fixture이며 실장비 성공을 뜻하지 않는다.

backend에서 실행:

```sh
python -m pytest tests/test_observation_contract.py -q
python -m pytest -q
```

JSON Schema는 Pydantic 모델의 model_json_schema()로 생성한다. tests/test_observation_contract.py가 배포 스키마 일치, 예제 round-trip, 범위·결측·UTC·근거·수정 연결 실패와 기존 DTO 호환성 경계를 검사한다.

Q-04의 품질·stale·음성 억제 임계값은 미정으로 유지한다. 이 계약은 임계값과 무관하게 필요한 정보를 보존하며 팀 담당자의 실제 어댑터 호환성 확인은 WI-03에서 수행한다. 스키마 통과를 최종 정상 판정이나 독립 안전 채널로 표현하지 않는다.
