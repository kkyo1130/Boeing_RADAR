# 운영·실입력·시연 안내

2026-10-17. 모의 환경의 재확인 보조 기능이다. 아래 소프트웨어 경로와 실제 장비 인수 결과는 구분한다.

## 시작

루트에서 `python3 scripts/bootstrap.py --speech`로 선택 음성 의존성까지 설치한다. 기존 설치라면 `.venv/bin/python -m pip install -r communication/requirements-local.txt`도 가능하다. 로컬 Whisper는 faster-whisper의 CTranslate2 모델 디렉터리를 사용한다. 원본 OpenAI checkpoint 파일과 구분하며 모델을 Git에 넣지 않는다. [제공자 공식 설치·로컬 모델 안내](https://github.com/SYSTRAN/faster-whisper)를 따른다. 실행 시 자동 다운로드하지 않는다. PyAV는 실제 확인한 호환성 때문에 19 미만으로 제한했다.

Backend에서 `../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`, 별도 터미널 frontend에서 `npm run dev`를 실행한다. 기존 DB의 추가 테이블은 lifespan 또는 `python -m app.migrate_contract_storage`가 비파괴 생성한다.

- `/`: 기존 수동 태블릿 MCP. Vision에 숫자를 직접 보내지 않는다.
- `http://localhost:5173/operations`: 운영 화면. START FLIGHT → 새 지시 준비 → 검사 설정 JSON 확인 → 생산자 입력 → 근거/사건 확인 → END FLIGHT → 종료 리포트.
- Vite의 `/api` 프록시 기본 대상은 `http://127.0.0.1:8000`이며 개발 시 `RADAR_API_TARGET`으로 변경할 수 있다.

기본 폼에서 호출부호·고도/방위·모의 점수를 확인할 수 있으며, 조건·순서 변경은 고급 설정을 사용한다. 검사 설정 예시는 [모의 정책](../../contracts/rule-policy-demo.json)을 `rule_policy`로 넣고, 실제 확인한 호출부호·조건·행동 순서를 입력한다. 관측 후에는 같은 지시의 설정을 변경할 수 없다. 새 지시를 준비한다. 예:

```json
{
  "confirmed": true,
  "confirmed_by": "operator",
  "rule_policy": {
    "policy_id": "mock-demo/1",
    "max_altitude_feet": 60000,
    "max_altitude_change_feet": 6000,
    "max_heading_change_degrees": 90,
    "change_window_seconds": 10
  },
  "minimum_model_score": 0.5,
  "atc_context": {
    "expected_callsign": "RADAR1",
    "expected_conditions": [],
    "expected_ordered_actions": ["altitude 3000", "heading 270"]
  }
}
```

이 임계값은 모의 설정 예시다. 검증된 정확도나 운용 기준이 아니다. 음성은 기본 비허용, 중요 단계는 기본 억제다. 운영자가 중요 단계/교신 사용 여부를 직접 설정하며 서버도 최신 정책과 현재 MISMATCH 근거를 확인한다. Pilot 마이크 어댑터는 녹음 중 활동 lease를 서버에 보내 음성을 억제하고, 원본 음성 재생도 UI 음성을 억제한다. 요청·실제 브라우저 재생 시작·억제·사용자 확인을 따로 기록한다. 브라우저 음성 지원, 출력 장치, 실제 교신과 경고 재유입은 현장 검증이 필요하다.

## ATC 파일·Pilot 마이크

먼저 운영 화면에서 받은 ID와 로컬 모델 경로를 셸 변수 `RADAR_FLIGHT_ID`, `RADAR_CLEARANCE_ID`, `RADAR_WHISPER_MODEL`에 설정한다. 다음 명령은 저장소 루트 기준이다.

```sh
.venv/bin/python scripts/produce_observation.py --flight "$RADAR_FLIGHT_ID" --clearance "$RADAR_CLEARANCE_ID" --source ATC --channel atc-whisper-local audio --wav /path/to/atc.wav --model "$RADAR_WHISPER_MODEL" --callsign RADAR1
.venv/bin/python scripts/produce_observation.py --flight "$RADAR_FLIGHT_ID" --clearance "$RADAR_CLEARANCE_ID" --source READBACK --channel pilot-microphone audio --microphone --seconds 10 --model "$RADAR_WHISPER_MODEL" --callsign RADAR1
```

허용한 16-bit PCM WAV만 입력한다. 파일의 실제 원본 UTC 촬영 시각이 확인되면 `--captured-at`으로 전달한다. 생략한 파일은 시각 불명으로 보류되며 파일 수정 시각이나 재생 시각을 원본 시각으로 바꾸지 않는다. 오래된 녹음은 실시간 정상 판정에 사용하지 않는다. 과거 녹음의 STT 평가는 오프라인 평가로 분리한다. 마이크에는 OS 입력 권한과 PortAudio 지원이 필요하다.

기본 10초 고정 구간이며 자동 화자 분리/중첩 탐지를 제공하지 않는다. 파일 전체는 최대 10분, 각 구간은 최대 30초다. 구간 ID·원본 오프셋을 생성하고 실제 전송 구간 WAV를 DB 근거로 저장한다. 호출부호와 역할은 입력 순서로 추측하지 않는다. 역할은 명시한 채널 배정이며 호출부호는 transcript에도 인식되어야 한다.

구조화는 명시적인 altitude/heading 및 개별 숫자 단어 문법을 지원한다. `one thousand`, FL 발화, 복합 조건, 지원하지 않는 표현은 억지 변환하지 않고 null/사유·원문으로 보류한다. silence/약신호/클리핑을 표시하며 잡음·중첩·경고 재유입의 자동 탐지는 미구현이다. 운영자가 해당 구간에 이 문제가 없음을 직접 점검한 실험에서만 `--reviewed-channel`을 지정할 수 있다. 이 플래그도 모델 숫자를 승인하거나 점수를 정확도로 바꾸지 않는다.

## Vision 서버 전송·재관측

기존 Vision CLI로 실제 카메라와 ROI를 설정하고 스트림의 `events.jsonl`을 얻는다. [태블릿 안내](../../vision/docs/tablet-demo.md)의 명령을 따른다.

```sh
.venv/bin/python scripts/produce_observation.py --flight "$RADAR_FLIGHT_ID" --clearance "$RADAR_CLEARANCE_ID" --source COCKPIT --channel cockpit-camera vision --events /path/to/events.jsonl
```

`--events -`는 표준 입력의 실시간 JSONL도 받는다. 파일에 저장된 이벤트를 다시 보낼 때 원래 촬영/처리 시각을 보존하므로 오래된 이벤트는 거부된다. 영상 파일의 촬영 시각 미상은 null을 유지한다. 각 숫자 ROI를 업로드하고 기존 frame ID를 sample ID로 사용한다. 같은 최신 관측이 있으면 새 sample만 correction으로 연결한다. 재시작·재시도도 같은 frame ID를 새 샘플처럼 쓰지 못한다. 가림/끊김은 값이 아닌 null 또는 health로 전송한다.

## Trace·근거·리포트 계약

`GET /api/v1/flights/{id}/report`는 집계·단계 판정·사건·수정·관측·알림·피드백·시간순 Trace를 반환한다. `report.json`은 동일 내용을 내려준다. END는 종료 직전 상태를 고정하며, 미해결/보류는 완료로 바꾸지 않는다. 새 지시로 넘어간 사건은 SUPERSEDED로 남고 해결 건수에 포함하지 않는다. 이전 지시 판정은 교체 직전의 기록으로 표시한다.

운영 화면은 1.5초마다 서버 상태를 갱신한다. `POST /api/v1/flights/{id}/refresh`가 시각 경과에 따른 보류 전이를 기록한다. 입력 없이 UI도 닫혀 있으면 해당 시점의 지속적인 백그라운드 감시 이력은 생성되지 않으며 다음 조회/종료의 현재 판정에 freshness가 적용된다.

근거는 `POST /api/v1/clearances/{id}/evidence`에 PNG/JPEG/WAV raw body로 업로드한다. 최대 8 MiB·이미지 1600만 픽셀, 실제 형식 검사를 적용한다. 반환된 URL/ID를 관측에 참조한다. 다른 지시 경로는 404, 삭제는 410이며 `DELETE`는 파일 내용만 제거하고 삭제 이력을 유지한다. 자동 보존 기간 삭제는 없으며 운영자가 삭제한다. 외부 임의 파일 경로를 읽어주는 API는 없다. 이 프로토타입에는 로그인/사용자별 접근 제어가 없으므로 서버는 신뢰한 로컬 실험 환경에서 실행한다.

## 검증·평가·인수

```sh
python3 scripts/verify.py --http-smoke
cd frontend
RADAR_TEST_PYTHON=../.venv/bin/python npm run test:e2e
```

브라우저 최초 실행 전 frontend에서 `npx playwright install chromium`이 필요하다. 브라우저 검사는 별도 임시 DB와 18080/5173 포트를 사용하며 사용자 개발 서버와 동시에 띄우지 않는다. 생성된 테스트 DB는 OS 임시 폴더에 남을 수 있다.

서버를 별도로 띄운 상태에서 루트의 `.venv/bin/python scripts/demo.py --output /tmp/radar-rehearsal.json`은 **합성 fixture** 네 비행(정상·Readback 3000/290·Setting 3500/270·판독 불가)을 생성한다. 불확실한 중간 수정은 OPEN을 유지하고 새 정상 관측만 해결한다. 이 데모 근거는 fixture 참조이므로 원본 재생 성공이나 실장비 성공이 아니다.

평가 명령·데이터 분리·인수 기록은 [평가 안내](../../contracts/evaluation/README.md)를 따른다. 현재 코드는 실제 태블릿 카메라·Pilot 마이크 인수, 실음성 정답 세트, 두 실모델의 독립 평가, 발표 장비 반복 시연을 대신하지 않는다.
