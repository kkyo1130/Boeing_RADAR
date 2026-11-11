# 사람이 관제사 역할을 하는 데모

기본 시연은 한 사람이 관제사 역할로 마이크에 지시하고, 다른 사람이 파일럿 모드에서 복창하는 방식이다. 같은 마이크를 번갈아 사용한다. 역할은 화면에서 선택하며 음성으로 화자를 식별하지 않는다. 관제 녹음 재생 시험은 선택 기능으로 유지한다.

## 사용 순서

1. `/operations`에서 등록된 호출부호로 비행을 시작한다. 로컬 준비 설정은 `RADAR123`이다.
2. 장치 설정에서 마이크를 선택하고 **마이크 연결**을 누른다.
3. 기본값 **관제사 지시 (ATC) → 관제사 직접 발화**에서 **관제사 발화 시작**을 누른다.
4. **마이크 켜짐** 안내가 나온 후 관제사 역할 사람이 말하고 **녹음 종료 · 검증**을 누른다.
5. 인식 문장과 서버가 채택한 지시를 확인한다. 보류되면 다시 입력한다.
6. **파일럿 복창**으로 전환해 파일럿이 녹음하고 검증한다. 이후 태블릿 MCP의 값을 사람이 직접 조작하고 카메라 OCR로 비교한다.

시연 문장 예시: “Radar one two three, climb and maintain three thousand feet, heading two seven zero.” 고도 3000ft, 방위 270°를 기대한다. 이 문장은 발표자가 읽는 예시이며 인식 요청에 정답으로 전달하지 않는다. 숫자나 호출부호가 잘못 인식되면 원문과 보류 사유를 확인하고 다시 말한다. 녹음은 29초 미만으로 한다.

## 실행

기존 [BERT+규칙 설정](bert-hybrid-stt-integration.md)의 Python 환경, `.demo/model`(faster-whisper), `.demo/bert-hybrid-model`, `.demo/config.json`과 frontend 의존성이 필요하다. `RADAR_NER_MODEL`, `RADAR_WHISPER_MODEL`, `RADAR_V2_CONFIG`, `RADAR_PYTHON`으로 경로를 지정할 수 있다. 이 변경은 학습 가중치를 수정하지 않는다.

```sh
sh scripts/run-live-demo.sh
```

Node 24 환경에서 실행한다. 기본 프런트엔드는 `http://127.0.0.1:5178/operations`, 서버는 8018 포트다. `RADAR_FRONTEND_PORT`/`RADAR_PORT`로 변경할 수 있다. 사용 중인 포트가 있으면 중단하며 기존 서버를 종료하지 않는다. 서버 준비에 실패하면 화면 서버도 시작하지 않는다. 카메라를 사용할 때는 기존 OCR 실행 파일을 `RADAR_OCR_BINARY`로 지정한다.

이번 로컬 재생 시험은 기존 일반 Whisper `base.en`과 BERT+규칙 v3를 사용했다. 깨끗한 발화에서의 성능을 실제 무전 환경의 정확도로 해석하지 않는다. 관제 전용 Whisper로 바꾸려면 모델 경로를 명시하고 별도 평가한다. 호출부호 프롬프트는 기본 활성화하지 않는다. `RADAR_STT_CALLSIGN_CONTEXT=1`을 별도 설정하면 기존 `callsign_context_requires_review` 보류 정책이 그대로 적용된다.

## 입력과 판정

브라우저 마이크 PCM → 로컬 Whisper 전사 → BERT 호출부호 + 고도·방위 규칙 → 서버 지시 연결·복창 비교 순서다. 직접 발화는 `input_mode=microphone_live`, 구간의 역할 근거는 `ATC_DEMO_MICROPHONE`이다. 재생은 기존 `microphone_playback`/`ATC_PLAYBACK`, 파일럿은 `PILOT_PTT`를 사용한다. 실제 무전 수신을 뜻하지 않는다.

녹음 시작 시 역할·입력 방식·현재 ATC ID를 고정한다. 녹음과 처리 중 모드 전환을 막고, 직접 발화와 파일럿은 브라우저 소음 억제·에코 제거를 요청한다. 스피커 녹음 재생은 재생 음성이 제거되지 않도록 두 기능을 끈다. 실제 처리 지원 여부는 브라우저와 장치에 따른다.

무음·미인식·해석 실패·취소를 정상으로 바꾸지 않는다. 새 ATC가 채택되지 않으면 이전 지시에 대한 복창을 진행하지 못한다. Cockpit 설정을 자동 변경하지 않으며, 복창 일치만으로 전체 검증 완료가 되지 않는다.

## 검증 근거

- 백엔드 627개(실제 BERT/v7 로딩 포함), HTTP 통합 47개, 프런트엔드 단위 54개, 계약 Schema 6개/fixture 22개 통과.
- Playwright 2개: 직접 발화와 녹음 재생 각각 ATC→Pilot 연결, 녹음 중 역할/입력 고정, 취소 후 이전 지시 사용 차단. 브라우저 미디어와 ASR 경계는 테스트용 가짜 입력이다.
- 기존 사용자 마이크 WAV를 실제 로컬 STT로 재처리: `Radar, one, two, three, climb and maintain, three thousand feet, heading to seven, zero.` → RADAR123/3000ft/270°. 같은 녹음의 복창은 NORMAL. 합성 290° 복창은 MISMATCH. 새 관제 무음은 `silence_or_weak_signal`, `LATEST_ATC_NOT_ADOPTED`; 이전 지시 ID로 복창 시 HTTP 409.
- 재현: `scripts/test-live-atc.py --wav <기존-마이크.wav> --wrong-heading-wav <합성-290도.wav> --output <로컬-결과.json>`. 서버 URL은 `--server`로 지정한다. 재생 시험의 요청 시각은 합성 순서 시각이며 원래 녹음 시각이 아니다. 원음·모델·DB·결과 JSON은 Git에 포함하지 않는다.
- 새 실시간 2인 발화, 잡음 있는 발표장, 실제 무전 수신, 카메라와 동시 시연은 이번 검증에 포함하지 않았다. 이 문서는 관찰한 로컬 결과와 구현을 기록하며 운항 성능 평가를 대체하지 않는다.
