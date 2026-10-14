# 공통 관측 생산자·소비자 통합 검증

SPEC-002-WI-03의 fixture 기반 통합 검증이다. 실제 Vision·STT·SDR 어댑터나 장비 검증은 아니다. 제품 코드는 바꾸지 않고 [공통 계약 예제](../../contracts/examples/observation-v1)를 Mock 생산자로 전송한다.

backend에서 설치된 의존성 환경으로 실행한다:

```sh
python -m pytest ../tests/integration -q
python -m pytest tests ../tests/integration -q
```

독립 Mock 생산자는 서버 Pydantic 모델을 import하지 않는다. 예제의 값·단위·null·실패 사유·품질·점수·근거를 유지하고, 새 합성 샘플에 테스트 비행/예약 지시 ID·고유 이벤트/관측/샘플 ID·제어된 UTC 시각을 부여한다. 음성 역할은 fixture 라벨로 지정한다. 원본 녹화/녹음 시각을 바꾸는 실입력 어댑터가 아니며 실제 자료에는 사용하지 않는다. fixture 근거 참조는 설명용으로 실제 파일 존재를 보장하지 않는다.

| 완료 조건 | 검증 근거 |
| --- | --- |
| AC-01 버전·부분값·품질·근거 계약 | 기존 backend/tests/test_observation_contract.py + 통합 요청/저장/조회 대조 |
| AC-02 수신·지시 연결·중복/시간 경계 | 기존 backend/tests/test_contract_receiving.py + 새로운 지시·수정·UTC 재시도 통합 |
| AC-03 생산자/소비자 동일 의미 | tests/integration/test_contract_producer_integration.py 전체 |

통합 시나리오:

- ATC/Readback/Cockpit의 정상 입력: 원본 필드·단위·시각·근거·역할이 저장/조회 후 유지된다.
- 부분 지시: ALT 비요청 null과 HDG 숫자 0이 세 source에 유지된다.
- 판독 불가: ALT value=null과 blank_roi 사유를 보존한다.
- 시각 미상: null 촬영 시각을 저장하되 accepted=false로 최신 관측 교체를 막는다.
- 장치 장애: health는 새 숫자/근거를 만들어내지 않고 해당 채널의 보류 사유가 조회된다.
- 수정 재관측: 새 샘플·관측 ID로 이전 관측을 참조하고 전후 이력을 보존한다. 정확한 재시도는 이력을 늘리지 않는다.
- 새 지시: 이전 지시는 비활성화되고 새 지시에는 이전 관측이 복사되지 않는다. 이전 요청 재생은 receipt만 반환한다.
- 버전·단위·null 사유 위반: 422이며 이력에 저장하지 않는다.
- UTC의 Z와 +00:00은 같은 시각으로 비교하며 동일 이벤트 재시도도 동일하게 처리한다.

SQLite는 매 테스트의 임시 DB를 사용하고 서버 시계는 제어한다. JSON 직렬화→TestClient HTTP API→DB→조회 경계를 검증한다. 외부 네트워크/실제 Uvicorn 서버·카메라·마이크·SDR·OCR/STT 모델 성능은 미검증이다. 서버의 수신 accepted를 정상 판정으로 해석하지 않으며 정책·확인 문맥을 등록하지 않은 이 통합 fixture의 상태는 UNVERIFIED다. SPEC-005-WI-02의 판정 활성화 검증은 backend/tests/test_three_state_decision.py에서 수행한다. Closed-loop 해결 상태·실제 근거 파일 저장/권한은 후속 스펙 범위다.
