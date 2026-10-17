# SPEC-002 생산자·소비자 HTTP 통합 검증

저장소 루트에서 backend 의존성이 설치된 Python을 사용한다. macOS/Linux의 로컬 TCP 포트와 subprocess 실행이 필요하다. 외부 API·카메라·마이크·모델·기존 서버·기존 DB는 사용하지 않는다.

```sh
backend/.venv/bin/python -m pytest tests/integration -q --basetemp=/tmp/radar-contract-http-run-1
```

`--basetemp`는 pytest가 초기화하는 **폐기 가능한 테스트 전용 경로**로 지정한다. 실행을 비교하려면 다음 실행에 다른 경로를 준다. 샌드박스가 localhost bind를 막으면 실행 환경에서 로컬 네트워크 권한이 필요하다. 검증을 건너뛰거나 TestClient 결과를 실제 HTTP 성공으로 기록하지 않는다.

테스트가 직접 임시 SQLite DB와 별도 uvicorn 프로세스를 만들고 종료 시 프로세스를 회수한다. 임의 포트에 먼저 bind한 listening socket을 uvicorn에 전달하므로 포트 선정과 서버 시작 사이의 경쟁을 피한다. 서버 준비를 최대15초 확인하고, HTTP 요청 제한시간은5초다. 환경의 HTTP proxy는 사용하지 않는다.

mock 생산자 [mock_producer.py](mock_producer.py)는 backend DTO·서비스·ORM을 import하지 않는다. [기존 v2 예제](../../contracts/examples/v2/)와 [통합 fixture](../../contracts/examples/integration/)에서 JSON을 만들고 공개 JSON Schema로 요청/접수/오류/목표 snapshot을 검사한 뒤 실제 HTTP로 전송한다. 서버 내부의 시각·DB·서비스 함수를 monkeypatch하지 않는다. DTO의 교차 제약은 실제 서버의422 응답으로도 확인한다.

원본 시각·ID·목표 revision은 매번 실행 시 생성/조회한다. 품질은 `cases.json`이 **명시한 합성 입력**이며 실제 모델 점수나 정확도가 아니다. VALID 예제의 테스트 품질만 설정하고 UNREADABLE 필드의 null/사유/품질은 보존한다. `config.json`의 규칙 상한50000ft/목표 급변10000ft/방위180도와60초/0.1초/0.5점은 여유 있는 fixture 설정으로 운용 기준을 제안하지 않는다. `fixture-audio-*`는 mock 구간의 참조 문자열이며 실제 녹음·미디어 재생 검증을 뜻하지 않는다.

각 테스트의 임시 디렉터리에 `exchange.json`을 남긴다. 실행 ID, 전송/응답 UTC 시각, HTTP 경로, 요청 JSON, 응답 코드·본문을 기록하며 실패한 HTTP 응답도 보존한다. 별도 비행 재실행 사례는 `second-exchange.json`도 남긴다. 서버 로그·DB는 `http-backend0/`에 있다. 실행 기록과 DB는 Git에 추가하지 않는다.

| 검증 묶음 | 관찰 내용 |
| --- | --- |
| 유효 입력·0/null | HDG0은0으로, 판독 불가 ALT는null+blank_roi로 저장. 요청 원본·접수 event_id·Trace 대응 |
| 부분 지시·복창 | ALT B/4000과 HDG A/270의 소유 지시·관측 출처 유지. B 복창은 호출부호+ALT만 요구 |
| 미인식 | UNKNOWN 범위/NEEDS_REVIEW 추출을 부분 성공으로 채택하지 않음 |
| 카메라 장애 | DISCONNECTED/AVAILABLE은 현재값을 비우며 이전 프레임 재포장으로 복구하지 않음 |
| 새 지시·재관측 | 변경된 목표에 이전 revision/촬영 시각 사용 불가. 변경되지 않은 항목의 적용 출처 유지, 새 적격 프레임 적용 |
| 버전·단위·연결 | 미지원 버전, FL 단위,360도, VALID+null, UTC 누락/시각 누락, 다른 비행을422/409로 거부. 부분 저장 없음 |
| 시간·revision | stale/future/unknown을 수신 시각으로 정상화하지 않음. 서버보다 큰 revision은409 |
| 중복·비동기 순서 | 동일 재송신200 같은 event_id, 내용 충돌409. 취소 Pilot·이전 ATC 배제. 먼저 도착한 Pilot은 같은 등록 ATC 채택 후 적용 |
| 실행 격리·기존 경로 | 새 실행의 ID·비행·이력 분리, 다른 비행 원본 재사용 거부, v1 시작과 v2 종료 후 변경 거부 |

정상 접수는 수신 계약 성공이다. 최종 숫자 비교는 SPEC-005-WI-02에서 추가한 state.validation으로 검사하며 수신/구조 규칙 PASS와 구분한다. 실제 생산자 어댑터, STT/OCR 성능, 물리 장치, 경고·Incident·리포트 전체 E2E 성공은 주장하지 않는다.

전체 SPEC-002 검증은 아래 검사를 함께 실행한다. 첫 검사는 스키마6종·예제21개의 Schema/DTO 기대값, 마지막 검사는 기존 API·migration·원자성 등의 백엔드 회귀다.

```sh
backend/.venv/bin/python contracts/check_v2.py
cd backend
.venv/bin/python -m pytest -q
```

SPEC-005-WI-01 이후에는 합성 구조 규칙 정책도 비행별로 고정한다. 기존21개에 명시 FL 통과·모델 PASS/원문값 충돌 거부·미지원 조건 보류3개를 추가해 현재 HTTP 통합은24개다. 규칙 결과의 공개 JSON Schema와 원본/Trace의 관측 ID 대응도 검사한다. 최초 WI-03의21개 수행 기록은 당시 근거로 유지한다.

SPEC-005-WI-02에서 정상/조기 일치→즉시 재불일치와 Cockpit 미입력 중 복창 오류 우선2개를 추가해 현재 HTTP 통합은26개다. validation-snapshot-v1 Schema·판정/Trace 대응을 확인한다. 정밀5초 경계·부분 지시·타이머 rollback은 backend 가상 시계 테스트다. 과거 UNVERIFIED 고정 설명은 당시 수신 구현의 한계이며 현재 최종 비교는 state.validation을 사용한다.
