# 결정론적 구조화 검사 v1 · SPEC-005-WI-01

음성의 ATC/READBACK 추출 결과를 같은 원문 transcript·등록 구간·호출부호·설정 정책과 대조한다. 모델의 `instruction_check`와 별개로 서버가 계산하며, AI 재질문·다른 모델 호출·음성의 재인식은 수행하지 않는다. 같은 ASR 원문을 쓰므로 독립된 센서나 검증된 안전 채널이 아니다.

실행 원본은 [검사 서비스](../backend/app/services/structure_rules.py), [타입](../backend/app/schemas/structure_rules.py), [문형 fixture20개](examples/structure-rules/cases.json)다. [정책 Schema](schemas/structure-policy-v1.schema.json)와 [결과 Schema](schemas/structure-result-v1.schema.json)는 Draft2020-12이며 backend 회귀가 DTO와 JSON의 일치를 확인한다. 기존 공통 v2 Schema6종은 그대로 유지한다.

## 입력·출력과 적용

입력은 v2 DTO 검사를 통과한 ATC/READBACK의 원본 dict, 서버에 등록된 구간·지시 ID, 비행별 등록 별칭·이전 항목 목표와 규칙 정책이다. 별도 순수 규칙 테스트에서는 타입/범위 위반도 직접 주입한다. Cockpit 숫자 비교, 실제 음성의 진실성, freshness/품질 판정과 최종 NORMAL/MISMATCH/UNVERIFIED는 이 함수의 책임이 아니다. freshness·품질·취소/이전 시도·장애는 기존 수신 검사와 함께 적용한다.

결과에는 `rules_version="1"`, observation/flight/segment/attempt ID, `policy_ref`, 원문에서 유도한 `derived_values`, 검사별 rule/field/result/reason, 종합 result를 담는다. `derived_values`는 원문 대조용이며 생산자의 `fields`를 덮어쓰거나 자동 수정하지 않는다.

| result | 의미·처리 |
| --- | --- |
| PASS | 구현된 문형·문맥·정책 검사가 통과. 수신의 다른 보류 사유를 해제하지 않으며 최종 정상/해결을 뜻하지 않음 |
| INVALID | 명확한 범위·단위·문맥·원문/추출값 충돌 또는 명시 정책 상한 위반. 목표/현재 숫자 적용 금지 |
| NEEDS_REVIEW | 지원하지 않는 문형/조건, 판독 불가, 미상 범위, 정책 누락, 급변 검토 필요. 목표/현재 숫자 적용 금지 |

종합 결과는 INVALID → NEEDS_REVIEW → PASS 순서다. 각 검사 사유는 모두 보존한다. 모델 `instruction_check=PASS`여도 서버 INVALID/NEEDS_REVIEW를 무시하지 않는다. 반대로 서버 PASS가 모델 INVALID/NEEDS_REVIEW나 낮은 품질·stale 입력을 승격하지 않는다.

## 지원 문형과 수치

원문은 등록 호출부호 표현으로 시작해야 한다. 대소문자·공백·쉼표/마침표를 정규화한 뒤 전체 문장을 소비하며, 중간에 맞는 숫자만 찾아 나머지 텍스트를 버리지 않는다. 유사 발음을 추정해 별칭을 추가하지 않는다. 등록 표현이 여러 개 겹치면 NEEDS_REVIEW다.

- ALT: `climb and maintain ...`, `descend and maintain ...`, `maintain ...`. 숫자에 `feet`, `flight level` 또는 명시 `FL`이 필요하다.
- HDG: `heading ...`, `turn left heading ...`, `turn right heading ...`.
- 두 항목: ALT 문형 다음 HDG 문형. 연결어 `and`는 선택이다. 부분 지시는 원문/mentioned_fields/fields 집합이 정확히 같아야 한다.
- 숫자: ASCII 숫자 또는 zero/oh~nine/niner의 자리별 발음. feet는 one~nine thousand와 선택 one~nine hundred 조합도 지원한다. 그 밖의 수사 문형은 NEEDS_REVIEW다.
- FL은 정확히3자리다. `FL040`/`flight level zero four zero`를4000ft로 유도하고 이미 정규화된 value와 비교한다. 정규화 단위는 항상ft이며 FL을 wire unit으로 받지 않는다. HDG는0~359이며360을0으로 보정하지 않는다.
- 필드 `raw_text`도 같은 숫자/명시 FL·feet 문법으로 대조한다. FL 표시의 원문은 `FL040`처럼 단위를 남겨야 한다. 누락/지원하지 않는 원문은 NEEDS_REVIEW, 추출값과 명확한 충돌은 INVALID다.
- if/after/before/until/when/then/unless 조건·순서는 NEEDS_REVIEW다. 호출부호가 끝에 오는 복창, 지원하지 않는 어순·추가 명령도 자동 통과하지 않는다.
- 파서 자원 경계는 호출부호 뒤 명령2048자, 필드 원문128자다. 초과 입력은 NEEDS_REVIEW다. 운항 수치나 모델 성능 기준이 아니다.

등록 flight/segment/atc_input/attempt/역할과 READBACK instruction ID를 재확인한다. 원본 시각은 등록 구간 시작과 같아야 하며 처리 시각은 구간 끝보다 이르면 안 된다. 취소·최신 시도 여부는 수신 서비스가 선행 검사한다. 서로 다른 ATC·시도를 다시 연결하지 않는다.

## 명시 정책과 시연 설정

`RADAR_V2_CONFIG`에 선택 `structure_rules`를 추가한다. 생략/null은 기존 설정 파일을 파싱할 수 있지만 필요한 상한·급변 검사에 NEEDS_REVIEW를 남긴다. 자동 운용 기본값은 없다. 정책을 바꾸면 새 비행을 시작해야 하며 실행 중인 비행의 snapshot은 바뀌지 않는다.

| 필드 | 형식·의미 |
| --- | --- |
| policy_ref | 비어 있지 않은 설정 근거/버전. 실제 검증 자료 또는 합성 fixture인지 명시 |
| max_altitude_ft | 0 이상 정수 또는null. 명시 상한 초과 INVALID, 상한과 같으면 통과 |
| max_altitude_change_ft | 0 이상 정수 또는null. 기존 ALT 목표와 새 ATC 목표 차이 초과 NEEDS_REVIEW, 같으면 통과 |
| max_heading_change_deg | 0~180 정수 또는null. 방위의 짧은 원주 거리 차이 초과 NEEDS_REVIEW |

처음 목표를 채택할 때는 비교할 이전 지시가 없으므로 명시 급변 정책 아래 해당 기준 부재를 `INITIAL_TARGET_NO_CHANGE_BASELINE`으로 기록한다. 이후의 변화는 이전 **지시 목표값**과 비교하며 실제 항공기 상태나 상승/선회 속도를 계산하지 않는다. READBACK의 지시값과 다른 숫자는 구조 검사가 아니라 다음 WI의 복창 비교 대상이다.

[HTTP 테스트 설정](examples/integration/config.json)의50000ft/10000ft/180도는 기존 계약 사례와 경계 검증을 위한 **합성 시연 정책**이다. 실제 환경의 운용 상한·비정상 급변 기준·성능 인수 수치로 확정하지 않는다. 사용자가 정한 실측 목표가 없다는 사실을 성공 기준으로 바꾸지 않는다.

## 저장·조회·호환

`GET /api/v2/flights/{id}/state`에 ATC/READBACK별 최근 실제 검사인 `structure_checks`가 추가된다. 각 결과의 observation ID로 대상을 식별한다. 새 시도가 아직 검사되지 않았거나 장애가 발생해도 이전 검사 결과는 역사 정보이며 현재값/채널 상태를 대신하지 않는다.

`INPUT_RECEIVED` 및 `DEFERRED_READBACK_RECHECKED` Trace snapshot에 해당 입력의 `structure_check`를 남긴다. 취소/재사용/선행 ATC 미채택 등으로 이번 입력의 검사를 하지 않았으면null이며 이전 입력의 결과를 빌려 넣지 않는다. 원본 payload·상태·검사 근거는 기존 수신 트랜잭션 안에서 함께 저장/rollback된다. 같은 관측 재전송은 같은 접수 event_id를 반환하고 재검사를 중복 기록하지 않는다.

새 DB 컬럼·migration은 없다. 새 설정/검사 snapshot은 기존 v2 context의 JSON state와 Trace를 사용한다. 정책 snapshot이 없는 기존 v2 비행은 필요한 검사를 NEEDS_REVIEW로 처리하며 목표를 임의 채택하지 않는다. 기존 v1 경로·DTO·Trace는 변경하지 않는다. 최종 비교와5초 대기/오류 단계는 [WI-02 계약](validation-v2.md)에 연결했다. 규칙 PASS 자체가 전체 정상은 아니며 실제 음성/Incident 해결은 후속 작업이다.

## 검증

```sh
cd backend
.venv/bin/python -m pytest -q
```

공통 계약은 루트 `backend/.venv/bin/python contracts/check_v2.py`, 실제 HTTP 통합은 [실행 안내](../tests/integration/README.md)를 따른다. 문형 fixture·정확 경계·명시 FL·원문 충돌·정책 미설정·등록 문맥·재전송/원자성·공개 Schema 일치와 실제 HTTP 결과를 각각 검사한다. 구현·실행 결과·리뷰·인수인계의 원본은 [WI-01](../docs/spec/005-safe-validation/workitem/wi-01.md)이다.
