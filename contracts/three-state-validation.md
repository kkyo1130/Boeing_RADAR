# 3상태 판정 — SPEC-005-WI-02

`GET /api/v1/clearances/{clearance_id}`는 verdict=**NORMAL / MISMATCH / UNVERIFIED**와 workflow status를 구분한다. [응답 스키마](../backend/app/schemas/validation_result.py)는 OpenAPI에 등록되어 있다. 기존 Mock API의 상태 의미는 변경하지 않는다.

## 정책·확인 문맥 등록

지시 예약 후 **첫 관측 전에** `POST /api/v1/clearances/{clearance_id}/validation-settings`로 정책과 확인된 지시 문맥을 한 번 등록한다. 이후 수정·재등록은 409다. 새 지시는 새 설정을 필요로 하며 이전 지시의 관측·설정을 복사하지 않는다. 설정 없이 수신한 기존 지시도 계속 조회되지만 UNVERIFIED다. 관측이 들어온 뒤 설정을 소급 등록할 수 없다.

요청 예제(모의 fixture 전용):

```json
{
  "confirmed": true,
  "confirmed_by": "fixture-operator",
  "rule_policy": {
    "policy_id": "mock-demo/1",
    "max_altitude_feet": 60000,
    "max_altitude_change_feet": 6000,
    "max_heading_change_degrees": 90,
    "change_window_seconds": 10.0
  },
  "minimum_model_score": 0.5,
  "atc_context": {
    "expected_callsign": "RADAR1",
    "expected_conditions": [],
    "expected_ordered_actions": ["altitude 3000 feet", "heading 270 degrees"]
  }
}
```

confirmed는 필수 boolean true이며 confirmed_by는 확인 주체의 표시다. 인증된 사용자 신원 검증을 구현했다는 뜻은 아니다. 모의 환경에서 수동 확인 주체가 설정을 제공하며 생성형 추출 결과가 자기 검증 문맥을 자동 등록해서는 안 된다. 정책은 [WI-01 규칙 계약](extraction-rules.md)에 따른다. 모델 점수 0.5는 이 예제의 필터 기준일 뿐 정확도 50%나 실장비 검증 임계값이 아니다. null 문맥은 미확인, 빈 목록은 확인된 지시에 해당 조건/순서 요구가 없음을 뜻한다.

ATC를 확인된 문맥과 대조한다. Readback의 호출부호·조건·행동 순서도 확인 문맥과 대조하되 숫자 불일치는 문법 오류가 아닌 Readback 비교 오류로 처리한다. 지원하는 순서 표기는 `altitude N[ feet]`, `heading N[ degrees]`다. 순서·필드·단위를 유지한 채 해당 필드에서 읽힌 숫자를 대입해 형식/순서 검사하고, 그 숫자와 ATC 목표의 비교는 별도로 수행한다. Readback의 action 목록을 기대 목록으로 복사하지 않는다. 지원하지 않는 자유 문구·FL 행동 문법은 보류하며 STT 문법 확장은 후속 작업이다.

## 비교와 보류

ATC가 요청한 필드만 비교한다. 비요청 필드 객체 null은 결측 오류가 아니고, 요청 필드 value=null은 판독 실패다. 각 필드의 비교 가용성에는 다음 조건이 모두 필요하다.

- 지시가 활성 상태이고 비행이 종료되지 않았음
- 관측 시각이 알려져 있고 미래/지시 이전/stale 입력이 아님
- 해당 필드의 결정론적 검사 문제, 판독 실패, 낮은 품질이 없음
- 필드 모델 점수가 명시 정책 이상이고 근거 참조가 available임
- 채널 health가 available이고 최근 실패/거부 입력에 의해 이전 관측이 가려지지 않음

단순 판독 실패·낮은 모델 점수·규칙 충돌을 숫자 불일치로 바꾸지 않는다. 독립적으로 비교 가능한 필드에 실제 불일치가 있으면 다른 필드의 판독 실패와 함께 표시할 수 있다. 호출부호/조건/순서·채널·시각 같은 전체 문맥 문제가 있으면 해당 source의 숫자를 비교하지 않는다. ATC 보류면 후속 비교도 보류한다.

validation_context에는 등록된 정책·문맥·확인 주체와 시각을 반환한다. stages.atc/readback/cockpit에는 verdict, reasons, rules 결과, 비교 가능한 필드의 comparisons와 errors가 있다. reasons는 모든 보류 사유를 유지하며 errors는 확인된 숫자 불일치만 담는다. Readback 오류가 있으면 최종 READBACK_ERROR가 우선이다. Readback 정상일 때만 Cockpit 숫자를 비교하고, Cockpit 판독 실패는 해당 단계의 UNVERIFIED로 남긴다.

| 입력 결과 | verdict | status |
| --- | --- | --- |
| 세 단계 모두 fresh·검증 통과·숫자 일치 | NORMAL | VERIFIED |
| 확인 가능한 Readback 숫자 불일치 | MISMATCH | READBACK_ERROR |
| Readback 정상 + Cockpit 숫자 불일치 | MISMATCH | SETTING_ERROR |
| 필요한 근거/문맥/필드가 부족 | UNVERIFIED | UNVERIFIED |
| 새 유효 관측으로 Readback 오류 해결, Cockpit 미확인 | UNVERIFIED | RESOLVED(readback만) |
| 새 유효 관측으로 오류 해결 + 세 단계 정상 | NORMAL | RESOLVED |

resolutions는 해결된 source를 표시한다. status=RESOLVED만으로 전체 검증 완료 배지를 표시해서는 안 된다. 전체 정상은 verdict=NORMAL과 세 단계 결과를 확인한다. 새 숫자가 들어왔어도 낮은 품질·stale·규칙 충돌이면 해결하지 않는다. 보류된 중간 수정이 있어도 같은 source의 수정 참조 체인에서 확인된 이전 불일치와 최종 새 유효 관측을 연결한다. Incident 수명주기·최종 판정 이벤트 저장은 SPEC-007/008의 후속 범위다.

## 오래된 정상 방지

GET 시각마다 freshness와 상태를 다시 검사해 이전 VERIFIED/RESOLVED 배지를 유지하지 않는다. 거부된 최신 stale/미상/역순 입력은 이력에 남아 해당 source/channel의 이전 관측을 정상 근거로 사용하지 못하게 한다. 이후 새 유효 관측이 필요하다. 같은 서버 수신 시각에 거부·정상 이벤트가 섞이면 보수적으로 보류한다.

장치 unavailable/degraded 이후 available health만 도착해도 복구 전 숫자를 정상으로 재사용하지 않는다. 장애 시점보다 뒤의 새 관측이 있어야 한다. 수정 참조 체인의 시간·새 원본·ID 검사는 기존 수신 서비스가 담당한다. 동일 요청 replay는 새 판정 이벤트나 새 관측을 만들지 않는다.

## 저장과 재현

기존 두 v1 테이블에 더해 `contract_validation_settings`를 추가한다. 설정·확인 시각을 저장하고 기존 관측/legacy 데이터를 변경하지 않는다. backend에서 기존 추가 마이그레이션을 다시 실행하면 된다.

```sh
python -m app.migrate_contract_storage
python -m pytest tests ../tests/integration -q
```

판정은 보존된 관측·확인 문맥·입력 이력과 조회 시각에서 계산한다. 품질·정책·시각의 실제 성능 인수는 별도다. fixture의 available 근거는 실제 파일 존재/접근 검증이 아니며 저장·권한은 SPEC-008 범위다. 현재 검증은 TestClient와 임시 SQLite이고 실카메라·마이크·STT/OCR·SDR·외부 HTTP 서버 및 다른 DB는 미실행이다. 생성형 추출과 같은 입력을 사용하는 규칙은 완전히 독립된 안전 채널이 아니다.
