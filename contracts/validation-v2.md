# 3상태 비교·오류 단계 v1 · SPEC-005-WI-02

v2 수신에 연결된 필드별 READBACK/SETTING 비교 계약이다. [구조 규칙](structure-rules.md)의 PASS와 정상 수신을 숫자 일치로 간주하지 않는다. 실행 원본은 [validation_v2.py](../backend/app/services/validation_v2.py), 공개 타입은 [DTO](../backend/app/schemas/validation_v2.py)와 [JSON Schema](schemas/validation-snapshot-v1.schema.json)다.

## 조회·저장

기존 `GET /api/v2/flights/{flight_id}/state`에 `validation`을 추가하고 최상위 result/reason은 해당 판정과 일치한다. 이 결과가 최종 비교의 원본이다. `current`는 기존 수신 적격성/원본 조회용 shape를 유지하므로 그 안의 기존 result=UNVERIFIED를 단계 판정으로 쓰지 않는다. targets/readback_required/원본 DTO·receipt·기존 v1 경로는 유지한다.

`validation`은 validation_version="1", result, phase, reason, representative_stage, readback/setting 단계의 result/fields, advisory_candidates를 가진다. 필드 결과에는 stage, field, instruction_id, observation_id, expected/actual, result, reason, wait_until이 있다. 부분 지시는 항목별 소유 지시와 원본 관측을 보존한다. CALLSIGN은 현재 목표를 소유한 지시별로 구분한다.

| 결과 | 의미 |
| --- | --- |
| NORMAL | 필수 단계/항목의 현재 유효한 비교값이 모두 정확히 일치 |
| MISMATCH | 확인 가능한 유효 값이 불일치. 비교 불가인 다른 필드도 함께 보존 |
| UNVERIFIED | 입력/목표/규칙 근거·호출부호·품질·freshness/문맥 부족, 장애 또는 최초 설정 변경 대기 |

확인 가능한 복창 오류는 설정 오류보다 우선한다. 지시를 막 채택해 새 복창을 기다리는 동안에는 기존 오류의 필드 정보는 유지하되 대표 안내 후보를 비운다. 새 복창에 확인 가능한 오류가 있으면 READBACK을 우선한다. 새 복창이 일치하면 다른 항목의 기존 SETTING 오류도 다시 대표 대상이 될 수 있다.

phase는 WAITING_ATC/READBACK/SETTING/MONITORING/ENDED다. MONITORING과 NORMAL도 실제 항공 운항 인증이 아니다. 종료 시 현재 결과는 UNVERIFIED/ENDED, 안내 후보는 비운다. v1의 VERIFIED/RESOLVED와 ClearanceStatus를 바꾸지 않으며 v2 Incident 해결을 생성하지 않는다.

## 유효성·항목별 연결

수신 시 적용 가능한 값만 비교한다. current의 instruction ID와 해당 목표 ID, 원본 관측 ID 및 READBACK 구조 검사 적격성을 확인한다. 새 Pilot 등록/취소는 해당 지시의 복창/호출부호 현재값을 비운다. 새 지시가 아직 미채택이면 이전 targets가 남아 있어도 전체 NORMAL로 만들지 않는다.

명확히 다른 **등록된** 호출부호를 유효한 원문·규칙·품질로 확인한 경우 CALLSIGN MISMATCH로 구분한다. 미인식/누락/등록 불명·구조 충돌은 UNVERIFIED다. 다른 호출부호의 숫자를 일치 근거로 채택하지 않는다.

시간 정책은 비행 시작 시 고정한 기존 freshness 설정이다. 확인 전 READBACK·CALLSIGN과 현재 COCKPIT을 검사하고 null/stale/future를 숫자 불일치로 단정하지 않는다. 유효할 때 지시별 복창/호출부호가 이미 전부 일치했다면 해당 instruction/observation ID·값의 완료 근거를 유지한다. 같은 지시를 계속 복창시키지 않고 새 카메라로 지속 감시한다. 새 시도/취소/health로 현재 복창이 비워지거나 다른 관측/값이 오면 이전 완료 근거로 새 입력의 freshness를 우회하지 않는다. 목표 지시도 다음 채택/종료까지 소유권을 유지한다.

CAMERA health의 끊김/복구는 설정 현재값을, MICROPHONE/SPEECH_API health는 복창 숫자와 호출부호 현재값을 비운다. 복구 health만으로 NORMAL이 되지 않으며 새 적격 관측이 필요하다. 최신 지시와 연결되지 않은 과거 PASS/일치를 재사용하지 않는다.

## 최초5초 대기·조기 완료·지속 감시

서버가 해당 지시의 필요한 복창 숫자와 호출부호를 모두 일치로 확인한 최초 수신 시각 t0를 지시별로 저장한다. 대기 시간은 사용자 결정 D-005-02의5초다. 같은 ID 재송신·동일 지시의 재확인으로 최초 t0를 재시작하지 않는다.

- t0+5초 전: 확인 가능한 설정 차이는 expected/actual을 보존하되 INITIAL_ADJUSTMENT_WAIT/UNVERIFIED로 표시하고 안내 후보에서 제외한다.
- t0+5초 정확 경계부터: 최신·유효 관측이 여전히 다르면 ADJUSTMENT_DEADLINE_MISMATCH다. 시간만 지났거나 판독 불가이면 MISMATCH를 만들지 않는다.
- 대기 중 해당 지시가 현재 소유한 필수 설정이 모두 일치하면 즉시 일치로 전환한다. 일부만 일치하면 전체 완료나 완료 이력을 만들지 않는다.
- 일치 완료 후 같은 목표에서 새 유효 관측이 달라지면 SETTING_DEVIATED_AFTER_MATCH로 즉시 안내 후보가 된다. 추가5초를 주지 않는다. 미인식/만료/장애는 보류하며 현재 NORMAL로 유지하지 않는다.
- ALT B/4000만 새로 채택하면 ALT의 새 타이머/복창만 추가하고 HDG A/270의 소유권·기존 확인/감시는 유지한다. B 복창에 HDG를 요구하지 않는다. B 복창 완료 후 ALT가 기다리는 동안에도 기존 HDG 재불일치를 숨기지 않는다.

숫자는 정규화된 선택값을 정확 비교한다. 허용 오차나 모델 점수 기반 숫자 보정을 추가하지 않는다. 생산자의 안정화/입력 품질 검사를 단일 불확실 프레임의 성공으로 대체하지 않는다.

## 부작용·호환 경계

입력 mutation 때 validation_memory(지시별 복창 확인 시각·필드별 설정 완료 ID)와 validation_snapshot을 기존 v2 JSON state에 저장한다. 입력·상태·타이머·INPUT_RECEIVED Trace의 validation은 같은 트랜잭션이다. commit 실패는 함께 rollback하며, 재전송은 상태/이벤트를 중복 생성하지 않는다. 새 DB 컬럼이나 migration은 없다.

GET은 사본에서 현재 시각으로 비교해5초 경계·만료를 반영하며 revision/DB/Trace를 쓰지 않는다. 백그라운드 작업·알림 재생은 실행하지 않는다. 소비자가 상태를 조회하면 그때 유효한 판정을 받는다. 실제 UI 갱신/푸시·교신 우선 재생·Incident 정책은 SPEC-006/007에서 연결한다. advisory_candidates는 확인된 대표 오류의 **후보 데이터**이며 재생 완료나 경고 전송 기록이 아니다.

기존 비행의 current에 새 instruction/구조 근거가 없으면 UNVERIFIED로 보류하고 새 입력을 요구한다. 기존 기록을 묵시적으로 NORMAL로 승격하지 않는다. 더 많은 전체 회귀·거짓 정상 검증은 SPEC-005-WI-03, 실제 음성/카메라 통합은 해당 파트 WI와 SPEC-009의 범위다.

## 검증

backend에서 `python -m pytest -q`, 루트에서 `python contracts/check_v2.py`와 [실제 HTTP 통합](../tests/integration/README.md)을 실행한다. 정확 시계 경계·조기 완료·부분 지시/감시·복창 우선·0/null·freshness/규칙·호출부호·재송신·취소/새 시도·원자성·종료와 Schema 일치를 검사한다. 상세 실행/리뷰/인수인계는 [WI-02](../docs/spec/005-safe-validation/workitem/wi-02.md)의 기존 결과 항목을 따른다.
