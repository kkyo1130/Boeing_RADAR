# v2 Incident 발생 건·재검증 계약

SPEC-007-WI-01의 서버 정책이다. 입력은 [수신 계약](receiving-v2.md), 비교는 [validation](validation-v2.md)를 그대로 사용한다. 실제 Vision/STT 재인식·안정화와 화면·음성 재생은 해당 파트의 후속 WI다.

## 조회와 명령

GET `/api/v2/flights/{flight_id}/state`는 `incident_version="1"`과 `incidents` 배열을 추가한다. 각 원소는 [incident-v1 Schema](schemas/incident-v1.schema.json)를 따른다. 기존 target·validation·접수 응답·legacy enum은 유지한다. 기존 v2 비행에 incidents가 없으면 빈 배열로 시작하며 DB 컬럼/migration을 추가하지 않는다.

POST `/api/v2/flights/{flight_id}/revalidate`는 활성 비행을 현재 서버 시각으로 재검증·저장하고 state를 반환한다(200). 없는 v2 비행404, 종료 비행409이며 기존 ContractErrorV2 envelope를 쓴다. 본문으로 값·지시·해결 상태를 받지 않는다. 새 관측 없이 과거 프레임을 수정값으로 만들 수 없다.

**시간 경과:** GET은 읽기 전용이며 현재 시각의 validation/current_check만 계산한다. 새 발생 건·해결·Trace를 만들지 않는다. 최초5초 조정 대기 만료만으로 새 오류를 영속화하려면 소비자는 validation.setting.fields의 wait_until에 맞춰 POST revalidate를 호출하거나 새 입력을 전송해야 한다. 백그라운드 스케줄러는 없다. GET의 동적 MISMATCH를 이미 저장된 발생 건/실제 음성 재생으로 오인하면 안 된다. POST는 명령마다 revision과 REVALIDATED Trace를 남기지만 같은 미해결 오류의 occurrence_id는 유지한다.

## 식별자와 전이

발생 건의 키는 `flight_id + instruction_id + stage + field + occurrence_id`다. occurrence_id는 서버가 만들며 stage는 READBACK/SETTING, field는 ALT/HDG/CALLSIGN이다. 서로 다른 단계·필드의 오류는 별도 발생 건이다. CALLSIGN은 READBACK에만 생긴다.

| 입력/사건 | 저장 동작 |
| --- | --- |
| 적격 필드 MISMATCH | 같은 지시·단계·필드의 OPEN이 없으면 새 occurrence 생성 |
| 같은 미해결 오류의 새 관측 | 같은 OPEN의 latest_evidence/current_check 갱신; 최초 탐지·첫 근거·알림/음성 완료 메타데이터 유지 |
| 누락·불명확·stale·장애 | OPEN 유지, 현재 확인은 UNVERIFIED; 정상/해결로 변환하지 않음 |
| 오류 이후의 새 유효 관측으로 해당 필드 일치 | 아래 해결 조건 충족 시 RESOLVED |
| 검증된 새 지시가 해당 필드를 대체 | OPEN → SUPERSEDED. resolved_at은 null, 이력 유지 |
| RESOLVED 이후 재불일치 | 새 occurrence. 이전 해결과 새 음성 자격을 구분 |
| 비행 종료 시 OPEN | ENDED_UNRESOLVED. 해결로 집계하지 않음 |

현재 적용 target의 지시 출처로만 대체를 판단한다. 새 ATC 등록·해석 실패·대상 외 발화는 대체 근거가 아니다. 부분 ALT 갱신 시 기존 ALT 발생 건만 SUPERSEDED가 되고 HDG의 지시·발생 건·탐지/음성 메타데이터는 유지된다. 해당 지시가 다른 필드를 계속 소유하면 CALLSIGN 발생 건도 유지한다. 늦은 옛 지시 결과로 종료된 발생 건을 재개하지 않는다.

## 해결 근거

현재 수신의 비행·지시·attempt·등록 구간·원본 시각·품질·채널·raw 구조 검사를 통과한 필드 판정을 사용한다. SETTING은 유효한 복창 확인과 현재 카메라 최신성도 충족해야 한다. producer의 SUFFICIENT는 해당 입력 계약이며 실제 카메라 안정화 성능을 검증했다는 뜻이 아니다.

해결에는 NORMAL 판정, 마지막 오류 관측보다 **뒤인** observed_at, 다른 observation_id, 다른 frame_id(SETTING) 또는 segment_id(READBACK)가 모두 필요하다. 새 ID를 붙인 같은 프레임/구간은 수신에서 SOURCE_SAMPLE_REUSED로 배제된다. 오래된/이전 revision·다른 시도·대체된 지시의 값과 복구 AVAILABLE만으로 해결할 수 없다. 이 정책 이전에 저장되어 원본 sample ID가 없는 값으로 해결 근거를 만들지도 않는다.

READBACK 수정은 새 발화에서 해당 지시가 현재 소유하는 필수 필드와 호출부호가 모두 NORMAL이어야 한다. 누락/판독 불가를 이전 발화 값으로 채우지 않는다. 한 필드가 맞아도 같은 수정 발화가 완전하지 않으면 그 복창 오류를 해결하지 않는다. 복창 RESOLVED는 설정 일치·전체 NORMAL과 별개다. SETTING 오류는 필드별로 해결하므로 HDG 오류가 남아도 ALT 오류만 해결할 수 있다.

## 시각·근거·저장

- detected_at은 서버 최초 탐지 UTC, first_check/first_evidence는 당시 판정과 원본 연결이다. last_mismatch_evidence는 마지막 유효 오류 관측으로 해결 시각 비교에 사용한다.
- latest_evidence는 가장 최근 연결된 관측, reobserved_at은 그 원본 촬영/발화 시각, reverified_at은 서버 재검증 시각이다. resolution_evidence와 resolved_at은 실제 해결 전이에만 채운다. close_reason으로 NEW_VALID_OBSERVATION/TARGET_REPLACED/FLIGHT_ENDED를 구분한다.
- frame/segment/attempt/observation ID와 evidence_refs 또는 evidence_unavailable_reason을 보존한다. 원본 입력·새 Pilot 구간 등록/취소 Trace를 지시/발생 건으로 역추적할 수 있다. 실제 MCP를 손으로 돌린 시각은 관측하지 않으므로 임의로 기록하지 않는다.
- notified_at과 voice_completed_at은 후속 알림 모듈을 위한 nullable 기록이며 이 WI에서는 null이다. 실제 알림/재생을 실행하거나 완료로 위장하지 않는다. 발생 건 갱신·부분 대체 시 기존 값은 보존하며, 후속 모듈은 실제 출력 시점에 원자적인 기록 계약을 추가해야 한다. 이 필드를 변경하는 공개 endpoint는 아직 없다.
- 현재 flight JSON 상태와 INCIDENT_UPDATED(발생 건의 변경 snapshot), 입력 원본/판정 Trace는 기존 SQLite writer 트랜잭션에서 함께 commit/rollback한다. 동일 입력 ID 재전송은 기존 접수 event_id를 반환하며 새 전이를 기록하지 않는다. 해결/대체/종료된 발생 건은 삭제하지 않는다.

후속 UI는 OPEN + current_check의 필드/사유를 사용해 미해결과 현재 확인 보류를 구분해야 한다. 전체 대표 validation이 새 복창을 기다려도 미변경 필드의 발생 건을 지우거나 음성 완료 이력을 초기화하지 않는다. SUPERSEDED/RESOLVED/ENDED_UNRESOLVED는 활성 오류/보류 음성 대상에서 제외한다. 실제 재생 취소와 교신 우선순위는 SPEC-006에서 연결한다.


## PR #11 리뷰 보완

부분 지시 이후에도 이전 지시가 소유하는 항목의 OPEN READBACK 오류가 있으면 그 이전 ATC 입력에 연결한 새 Pilot 구간을 수정용으로 등록할 수 있다. 기존 구간/시각/attempt 검사는 유지하며, 이미 대체된 ALT는 이 발화로 갱신하지 않는다. 이전 지시가 더는 목표를 소유하지 않거나 미해결 복창 오류가 없으면 과거 지시 신규 시도409를 유지한다. 현재 readback_required는 최신 지시를 가리킨다.

이 정책 이전에 저장한 음성 현재값의 segment/time만으로 새 Incident를 만들지 않는다. attempt ID와 Schema에 맞는 evidence_refs/부재 사유까지 검사하고 불완전하면 발생 건 생성·해결 근거에서 제외한다. 필드 validation의 MISMATCH/UNVERIFIED는 계속 조회할 수 있으며 다음 적격 새 관측으로 정상적인 추적을 시작한다.
