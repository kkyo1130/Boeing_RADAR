# v2 운영·입력·리포트

PR #4 통합 후 서버 판정/저장/화면은 dev의 v2 한 경로를 사용한다. `/operations`가 운영 화면, `/`가 태블릿 MCP다. 별도 `/operations-v1` 및 `/api/v1`은 제공하지 않는다. 기존 무버전 Mock API는 호환성 테스트용으로 유지한다.

## 실행

저장소 루트에서 `python3 scripts/bootstrap.py`로 설치한 후:

```sh
cd backend
export RADAR_V2_CONFIG="$PWD/../contracts/examples/integration/config.json"
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

위 config는 RADAR123 호출부호와 모의 정책을 가진 합성 테스트용 예시다. 실제 시험에는 [v2 수신 계약](../../contracts/receiving-v2.md)에 맞춰 운영자가 별도 파일을 준비한다. 다른 터미널에서 `cd frontend && npm run dev` 후 `/operations`를 연다. START FLIGHT로 만든 `FLT2-...` ID를 입력 어댑터에도 사용한다.

## 로컬 음성

선택 설치: `python3 scripts/bootstrap.py --speech`. 기존 로컬 faster-whisper 모델 디렉터리가 필요하다. 다운로드나 모델 정확도 검증은 자동 수행하지 않는다.

```sh
.venv/bin/python scripts/produce_observation.py --flight FLT2-실제ID --source ATC audio \
  --wav /absolute/path/atc.wav --model /absolute/path/model \
  --callsign RADAR123 --alias-key radar-one-two-three --alias-text 'Radar one two three' \
  --captured-at '실제 UTC 촬영시각' --complete-utterance --reviewed-channel
```

Pilot은 `--source READBACK`, WAV 대신 `--microphone --seconds 10`을 사용할 수 있다. 먼저 ATC가 v2에서 채택되어 있어야 한다. alias는 서버 config에 등록되어 있고 실제 원문 앞부분에 있어야 한다. 실행 시 voice 입력 token을 예약하고 다른 브라우저의 재생 중단 확인 후 녹음을 시작한다. 처리/전송 종료 시 token을 반환한다. 실패한 END는 화면의 입력 종료 확인으로 해제한다.

`--complete-utterance`는 명령의 시작/끝이 잘리지 않았다는 사용자 확인, `--reviewed-channel`은 중첩·잡음·경고 재유입을 사용자가 점검했다는 뜻이다. 자동 탐지 기능이 아니다. 한 발화 30초 이하만 허용하며 긴 음성을 임의로 잘라 새 지시로 채택하지 않는다. 원본 시각 미상/미완료/낮은 품질은 보류한다. 숫자/문법 처리는 기존 v2 구조화 함수를 재사용하며 최종 판정은 서버가 수행한다.

## Vision

[기존 촬영 안내](../../vision/docs/tablet-demo.md)의 vision-stream/1 JSONL을 전송한다. 캡처를 시작하기 **전에** `/api/v2/flights/{id}/state`에서 revision을 읽는다.

```sh
.venv/bin/python scripts/produce_observation.py --flight FLT2-실제ID --source COCKPIT vision \
  --events /absolute/path/events.jsonl --target-revision 5
```

revision 5는 예시다. 새 ATC가 채택되면 새 revision으로 어댑터/캡처를 다시 시작한다. 지원하지 않는 과거 revision은 기존 서버가 보류한다. stream이 캡처 당시 `target_revision`을 함께 제공하면 그 값을 우선한다. 카메라의 원본 시각과 frame_id를 보존하고 영상 파일은 UNKNOWN 시각으로 전송한다. health는 원래 emitted_at을 보존한다. PNG 근거는 서버에 업로드되어 기존 근거 패널에서 열린다. 실제 카메라·ROI·마이크·스피커·Whisper 품질은 별도 장비 인수 대상이다.

## 근거 파일과 리포트

공개 필드와 종료 의미는 [v2 확장 계약](../../contracts/operations-v2.md)을 따른다.

- `POST /api/v2/flights/{id}/media`: PNG/JPEG/16-bit PCM WAV raw body, 최대 20 MiB. 반환된 `evidence_id`, `ref`를 v2 `evidence_refs`에 넣는다.
- 읽기는 기존 선택 범위 근거 API/패널을 사용한다. 다른 비행의 파일을 읽거나 삭제할 수 없다. 임의 외부 URL은 가져오지 않는다.
- `DELETE /api/v2/flights/{id}/media/{evidence_id}`: 원본 bytes 삭제와 Trace 기록. 기존 관측은 보존하고 이후 미디어 접근은 410이다.
- `GET /api/v2/flights/{id}/report` 및 `/report.json`: v2 판정·관측·사건·Trace를 조회한다. END FLIGHT가 같은 트랜잭션에서 마지막 라이브 판정을 고정하며, 기존 `/state`의 종료 후 UNVERIFIED 정책은 유지한다.
- 종료 후 `/operations`에 리포트 요약과 JSON 다운로드가 표시된다. 이후 파일 삭제는 종료 리포트를 덮어쓰지 않는다. 파일 접근 응답/삭제 Trace가 현재 보관 여부의 근거다.

보고서의 정상/불일치/보류는 **항목 수**, 사건/해결/대체는 **발생 건 수**다. 모델 정확도나 운항 적합성을 뜻하지 않는다. 과거 v1 DB가 있으면 자동 삭제/변환하지 않는다. 원본 브랜치 커밋 `9380807`에 이전 구현이 보존되어 있으며 기존 v1 기록의 이관은 별도 작업이다.

## 재현

```sh
python3 scripts/verify.py --http-smoke
cd frontend
npx playwright install chromium
npm run test:e2e
```

이미 설치된 Chromium 사용 시 `RADAR_CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e`. HTTP 시연은 임시 DB에 정상/복창 오류/설정 오류/판독 불가를 만들고 종료 리포트까지 확인한다. 직접 실행은 `.venv/bin/python scripts/demo.py --output /tmp/radar-demo.json`이며 실행 중인 서버에 합성 비행을 추가한다. 오프라인 평가는 [평가 프로토콜](../../contracts/evaluation/README.md)을 따른다.
