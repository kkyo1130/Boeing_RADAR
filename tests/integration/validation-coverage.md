# SPEC-005 전체 회귀·거짓 정상 검증

검증 대상은 모의 fixture와 현재 v1 API다. 실제 모델/장비의 성능 평가나 위험 0의 증명이 아니다. [실패 주입 목록](../../contracts/examples/validation-safety-cases.json)은 정답 상태·사유를 미리 고정하며 추론에 제공하지 않는다.

| 완료 조건 | 근거 |
| --- | --- |
| AC-01 HDG/FL·원문/값·호출부호/조건/순서·급변 | backend/tests/test_extraction_rules.py 31개 + 안전 행렬의 원문/정책/문맥 실패 사례 |
| AC-02 fresh/가용/검증 입력만 비교, 두 오류·보류·해결 구분 | backend/tests/test_three_state_decision.py 28개 + 기존 수신 경계 및 혼합 오류/복구 통합 |
| AC-03 불확실·장애·혼합 오류가 거짓 VERIFIED를 만들지 않음 | test_validation_safety_matrix.py 52개, source 3개에 대한 정상 대조 후 실패 주입·근거/사유 조회 |

행렬은 정상/VERIFIED 상태를 먼저 확인하고 같은 지시에 새 수정 입력을 전송한다. 읽지 못함, 0/미상 모델 점수, 저하/미상 품질, 근거 누락, 원문 충돌/누락, 호출부호·조건·순서 충돌, 시각 미상·stale·미래 처리·역순, 상한 위반, 채널 저하를 주입한다. 음성 문맥 실패는 ATC/READBACK에 적용한다. 값 일치만으로 이전 정상 배지가 유지되지 않는지, 거부된 시각 입력도 기존 정상 근거를 가리는지 확인한다.

추가로 ATC/Readback/Cockpit 채널 장애→available health만 복구→여전히 보류→새 관측 후 정상 복원을 확인한다. 실제 Readback 숫자 오류와 Cockpit 장애가 섞인 경우 READBACK_ERROR와 해당 단계 보류 사유가 함께 조회되는지도 확인한다. 입력 원본·이력·확인 주체는 보존되며 불확실성 자체를 숫자 불일치나 RESOLVED로 만들지 않는다.

재현(저장소 루트):

```sh
python3 scripts/verify.py --component backend
```

전체 환경·자동 검증은 [개발 안내](../../docs/development/README.md)를 따른다. 기존 143개와 새 52개를 합쳐 Backend/계약/통합 195개다. 실제 결과·명령·미실행 항목은 [WI-03](../../docs/spec/005-safe-validation.md#wi-03)에 기록한다. 실장비·실제 모델 입력 전체 검증은 SPEC-009 범위로 남긴다.
