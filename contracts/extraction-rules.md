# 결정론적 구조화 검사 — SPEC-005-WI-01

[check_observation](../backend/app/services/validation/rules.py)는 공통 관측 계약을 받아 `PASS / INVALID / NEEDS_REVIEW`, policy_id, issues를 반환한다. 모델 호출·값 보정·자동 Cockpit 설정 변경은 없다. 기존 validation_service.py와 API 판정은 변경하지 않으며 서버의 3상태 판정 연결은 WI-02에서 수행한다.

| 결과 | 의미 |
| --- | --- |
| PASS | 지정된 구조·일관성·문맥 검사를 통과. 실제 인식 정답, 입력 freshness, 정상 운항 또는 독립 안전 채널을 증명하지 않음 |
| INVALID | 계약·범위·단위 변환·원문 값·확인된 구조화 문맥의 명시적 충돌 |
| NEEDS_REVIEW | 정책/원문/문맥/관측 부족, 장치 장애·낮은 품질, 급변 등 재확인 필요 |

모든 문제를 보존하고 INVALID > NEEDS_REVIEW > PASS 순서로 집계한다. 각 issue에는 code, field, expected/actual 및 해당 필드의 evidence_ids를 남긴다. 입력·기존 관측을 수정하지 않는다. invalid 정책/문맥 설정은 Pydantic 오류로 거부하고 임의 기본값을 사용하지 않는다.

## 입력과 규칙

관측은 ObservationContract 또는 해당 JSON object다. 잘못된 계약 구조·HDG value=360 등은 contract_violation/INVALID다. health 이벤트는 health_without_observation/NEEDS_REVIEW이며 숫자로 비교하지 않는다.

- ALT: 원문 숫자 1–5자리 또는 FL180/FL 180 형식(ASCII 숫자 정확히 3자리, 대소문자 허용)을 검사한다. FL 숫자×100을 이미 전달된 feet 값과 대조한다. 함수가 값을 수정하지 않는다. FL18, 줄바꿈된 FL, 잘못된 변환은 INVALID다.
- HDG: 원문 숫자 1–3자리를 value와 대조하고 0–359 범위를 검사한다. 000은 0이며 360을 0으로 보정하지 않는다.
- 음성의 영어 숫자 단어 등 지원하지 않는 raw_text는 NEEDS_REVIEW다. O→0 변환이나 누락 숫자 추측을 하지 않는다. STT 숫자 문법은 SPEC-004의 후속 범위다.
- 비요청 필드 객체 null은 건너뛰고, 요청 필드 value=null은 사유와 함께 NEEDS_REVIEW다. unavailable/degraded health·degraded/unknown 품질·시각 미상도 보류 사유를 남긴다.
- 음성 호출부호는 확인된 expected_callsign과 대소문자만 정규화해 정확 대조한다. 호출부호/역할 근거/Transcript 누락은 NEEDS_REVIEW다. 확실한 호출부호 불일치는 INVALID다.
- conditions와 ordered_actions는 확인된 지시의 구조화된 문자열 목록과 순서대로 대조한다. 대소문자·공백만 정규화하고 동의어·부정문·숫자 의미를 바꾸지 않는다. 조건 누락·추가나 순서 차이는 확인된 구조와의 충돌로 INVALID다. 자유 발화 의미를 새로 해석하는 검사가 아니므로 같은 의미의 다른 표현도 불일치할 수 있다. 상위 구조화 단계가 같은 표기를 사용해야 한다.

RuleContext는 expected_callsign, expected_conditions, expected_ordered_actions를 모두 명시한다. null이면 확인된 문맥이 없으므로 NEEDS_REVIEW다. 빈 목록은 **확인된 지시에 해당 조건/행동이 없음**을 뜻하며 미확인 문맥 대신 사용하지 않는다. 문맥은 비행 세션·확인된 관제 지시에서 제공해야 하며 같은 추출 값을 그대로 복사해 일치 근거로 만들지 않는다. Cockpit에는 음성 문맥 검사를 적용하지 않는다.

## 모의 시연 정책

[rule-policy-demo.json](rule-policy-demo.json)의 mock-demo/1은 이 WI의 재현용 정책이다. 실행 시 명시적으로 전달하며 제품 API가 자동으로 적용하지 않는다.

| 설정 | 시연 값 | 근거·적용 |
| --- | --- | --- |
| max_altitude_feet | 60000 | FL600을 통과 경계, FL601을 위반 fixture로 고정하기 위한 실험 상한. 기체 운용 한계 아님 |
| max_altitude_change_feet | 6000 | 연속 선택값 변화의 경계·초과 테스트용 |
| max_heading_change_degrees | 90 | 90° 경계와 91° 재확인, 359→0 순환 테스트용 |
| change_window_seconds | 10 | 같은 지시·source의 새 관측 10초 이내 변화에만 급변 검사를 적용 |

정책 미지정은 policy_missing/NEEDS_REVIEW다. 값은 별도 검증/팀 합의로 변경해야 하며 이 fixture 성공을 실장비 최적 임계값이나 정확도로 표현하지 않는다. Q-04의 실장비 인수 기준은 미정이다.

previous가 있으면 같은 flight_id/clearance_id/source의 관측인지 검사한다. 다른 지시·source, 시각 미상·비증가·같은 sample/observation ID는 NEEDS_REVIEW다. HDG 변화량은 원을 따라 짧은 각도 차이를 사용한다. 임계값을 **초과**하면 rapid_change/NEEDS_REVIEW이며, 정확히 임계값이면 통과한다. 급변이 명령된 변경인지 증거가 부족하므로 INVALID/수치 불일치로 단정하지 않는다. 초기 관측에 previous가 없는 것은 변화 비교를 생략한다는 뜻이다.

## 사용과 검증

```python
from app.services.validation.rules import check_observation

result = check_observation(observation_json, policy=demo_policy,
                           context=confirmed_context, previous=previous_observation)
```

backend에서:

```sh
python -m pytest tests/test_extraction_rules.py -q
python -m pytest tests ../tests/integration -q
```

고정 기대 결과는 test_extraction_rules.py에 있으며 기존 공통 계약 예제를 재사용한다. 구조·raw_text·문맥이 같은 추출 입력에서 나올 수 있으므로 이 규칙은 모델과 구현 방식이 다른 검사이지 완전히 독립된 안전 채널이 아니다. 모델 점수 threshold·실시간 freshness·근거 파일 접근·Readback/Setting 최종 오류 단계·해결 상태는 여기서 판정하지 않는다. 실제 카메라/음성 및 모델 추출 결과의 실장비 인수 검증은 별도다.
