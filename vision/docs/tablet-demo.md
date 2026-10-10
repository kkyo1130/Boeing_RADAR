# 태블릿 촬영 데모

2026-10-10 사용자 지정 환경: 실제 Cockpit 대신 태블릿의 모의 MCP를 카메라로 촬영한다. frontend는 수동 설정값 화면, vision은 촬영·인식·품질·근거 생산자다. 실제 항공 계기의 인식 성능을 검증한 것으로 보고하지 않는다.

## 1. 화면과 장비 고정

웹캠 구매가 필수 선행 조건은 아니다. 노트북 내장 카메라나 빌린 USB 웹캠으로 먼저 숫자가 충분히 크게 찍히고 초점이 유지되는지 확인한다. 내장 카메라는 태블릿을 카메라 쪽으로 향하게 고정한다. 배치·초점·해상도가 부족하면 별도 웹캠과 거치대를 준비한다. USB 장치 분리/재연결 검증은 외장 카메라에서 별도로 수행한다.

[frontend 실행](../../frontend/README.md) 후 같은 Wi-Fi의 태블릿으로 Network 주소를 연다. 가로 방향·화면 밝기·촬영 모드·확대 여부·카메라 위치·초점을 고정한다. 기본 MCP 확대 화면을 권장한다. 전체 조종석 보기로 바꾸면 숫자 창이 작아지고 ROI가 바뀌므로 재설정·재평가한다. 아래 계기는 고정 사진이며 선택값으로 사용하지 않는다. ALT/HDG 숫자와 IAS가 프레임에 충분히 크게 나오도록 배치한다. 자동 꺼짐·화면 회전은 기기에서 직접 설정한다.

## 2. 의존성·촬영 프레임·ROI

아래 명령은 저장소 루트 기준이다. Python 3.11+와 macOS OCR 바이너리가 필요하다.

```sh
python3 -m venv vision/.venv
vision/.venv/bin/python -m pip install -e './vision[capture,test]'
mkdir -p vision/.build
xcrun swiftc vision/native/ocr.swift -o vision/.build/radar-ocr
vision/.venv/bin/python -m radar_vision.setup --camera 0 --width 1280 --height 720 --output vision/output/tablet/frame.png
vision/.venv/bin/python -m radar_vision.setup --image vision/output/tablet/frame.png --speed --output vision/output/tablet/roi.json
```

카메라 권한은 사용 환경에서 허용해야 한다. index 0이 다른 카메라이면 장치 index를 바꾼다. 요청 해상도를 장치가 지원하지 않으면 실제 프레임 크기를 사용하며 설정 결과에 실제 크기를 기록한다.

ROI 도구 창에서 **고도 → 방위 → 속도 순서**로 숫자만 드래그해 선택하고 Enter/Space로 확정한다. 라벨·단위·테두리·다이얼은 제외한다. Escape로 취소하면 기존 설정을 덮어쓰지 않는다. speed를 빼려면 `--speed`를 생략한다. 이 도구는 OpenCV의 로컬 GUI를 사용하므로 데스크톱 환경이 필요하다. 좌표를 직접 JSON으로 작성해도 된다.

설정에는 해상도·ROI·단위·실험 점수 임계값만 있다. 정답 값은 넣지 않는다. 기본 ALT 단위는 feet, HDG degrees, 속도 knots다. snapshot의 촬영 시각은 센서 노출 시각이 아닌 **호스트가 프레임을 받은 시각**이며 `.metadata.json`에 남긴다. 촬영 프레임/설정/로그는 ignored output에 보관한다.

## 3. 정지 이미지 확인 후 스트림 실행

```sh
vision/.venv/bin/python -m radar_vision.cli vision/output/tablet/frame.png --config vision/output/tablet/roi.json --ocr-binary vision/.build/radar-ocr --output-dir vision/output/tablet/still
vision/.venv/bin/python -m radar_vision.stream --camera 0 --config vision/output/tablet/roi.json --ocr-binary vision/.build/radar-ocr --output-dir vision/output/tablet/live --duration 60
```

초기 정지 이미지 명령은 촬영 시각을 자동 추정하지 않는다. 필요하면 metadata의 `captured_at`을 `--captured-at`으로 명시한다. 스트림은 카메라 프레임의 호스트 수신 시각을 자동 기록한다.

기본 실험값: `--sample-seconds 1`, `--stable-frames 3`, `--read-timeout 3`, `--max-frame-age 5`, `--retry-seconds 1`. 실장비 평가로 확정된 기준이 아니다. 세 번 연속 같은 값이 읽혀야 `value`를 제공한다. 그 전에는 `value=null`, `reason=unstable_reading`이며 `candidate_value`는 진단용 값이다. 인식 실패·값 변경·끊김·재연결은 해당 안정화 기록을 초기화한다. 빠른 값 전환은 보류될 수 있으며 지연 목표를 보장하지 않는다.

카메라 읽기와 OCR은 별도 스레드이고 입력은 최신 프레임 하나만 유지한다. 연결 실패는 자동 재시도한다. 새 프레임이 없거나 OCR 처리 중 프레임이 오래되면 이전 숫자를 제공하지 않는다. 별도 감시 스레드는 OCR이 지연되어도 `latest.json`의 이전 관측을 health 이벤트로 교체한다. 카메라 드라이버가 오래된 영상을 새 프레임처럼 반복 반환하는 동결은 감지하지 못한다. 호스트 수신 시각은 센서/드라이버 버퍼의 지연을 증명하지 않는다.

## 4. 출력과 파일 재생

실행별 UUID 폴더에 `events.jsonl`, `latest.json`, 프레임별 원본·ROI·OCR 입력·`observation.json`이 생성된다. 결과는 **로컬 vision-stream/1 계약**이며 현재 서버 endpoint로 직접 전송하지 않는다. 상세 형식은 [스트림 결과](../README.md#스트림-결과)를 참고한다. duration 생략 시 Ctrl-C로 종료한다. 출력은 자동 삭제하지 않으므로 사용 후 보관 용량을 관리한다.

```sh
vision/.venv/bin/python -m radar_vision.stream --video /path/to/tablet-recording.mp4 --config vision/output/tablet/roi.json --ocr-binary vision/.build/radar-ocr --output-dir vision/output/tablet/replay
```

파일은 미디어 시간 기준으로 샘플링하며 OCR 처리 속도로 오프라인 실행한다. `input_mode=video_file`, `live_input=false`, `captured_at=null`이다. 미디어 위치를 현재 촬영 시각으로 바꾸지 않는다. 영상 종료는 `video_ended`, 프레임 0개는 `video_no_frames`, duration 중단은 `playback_stopped`로 남긴다. 손상된 영상의 중간 읽기 실패와 정상 EOF를 모두 구분하지는 못한다. 녹화 압축으로 사진에서 읽히던 숫자가 실패할 수 있다.

## 5. 인수 시나리오

1. ALT 3000/HDG 270: 세 번 연속 판독 후 새 값·시각·ROI 확인.
2. ALT 3500: 변경 직후 이전 3000 대신 보류, 안정화 후 3500 확인.
3. HDG 290, 000: 변경 후 안정화 확인. 0을 누락값으로 취급하지 않기.
4. 고도 숫자 가림: ALT null·사유 확인. HDG는 읽을 수 있으면 유지.
5. 손 가림·초점 흐림·반사: 인식/오인식/판독 불가를 수동 정답과 대조해 기록.
6. 카메라 분리: 이전 숫자 없이 health 이벤트 확인. 재연결 후 안정화부터 다시 시작.
7. ALT 16000→15000→10000→16000, HDG 240→220→240을 반복하고 관측·근거·시간을 대조.

서버 NORMAL/MISMATCH/UNVERIFIED, 관제 지시 연결, 수정 후 RESOLVED는 이번 로컬 스트림에 없다. SPEC-002와 SPEC-003-WI-04에서 별도 연결한다. 태블릿 촬영·실카메라·파일 재생·화면 캡처·mock 테스트를 구분해 보고한다.

기술 참고: [OpenCV VideoCapture](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html).

## 6. 다음 작업과 기록 방법

현재 화면·촬영 도구·로컬 스트림은 구현됐고 화면 캡처 OCR과 합성 영상 검증까지 수행했다. 실제 태블릿을 카메라로 촬영한 결과는 아직 없다. 다음 순서로 SPEC-003-WI-01~03의 미검증 조건을 확인한다.

1. 사용할 카메라로 정지 프레임을 저장하고 숫자 크기·초점·반사·실제 해상도를 확인한다.
2. 촬영 모드/확대/배치를 고정하고 실제 프레임으로 ROI를 설정한다. 화면 캡처용 ROI를 재사용하지 않는다.
3. 정지 이미지 OCR을 정답과 대조한 뒤 60초 스트림을 실행하고 위 인수 시나리오를 반복한다.
4. 설정 변경부터 올바른 안정값이 나온 시점까지의 지연, 오인식, 보류, 장애/복구를 기록한다. 가림인데 숫자가 나온 경우도 실패로 남긴다.
5. 실촬영 근거를 확보한 뒤 SPEC-002 공통 계약을 확정하고 WI-04의 서버 전송·지시 연결을 구현한다. WI-05 전체 인수는 서버 연동 후 수행한다.

실행별 기록은 `vision/output/tablet/` 아래에 보관하고 공유 가능한 작은 샘플과 익명화한 요약만 검토 후 Git에 추가한다. frontend 정답은 사람이 별도 평가 기록에 적으며 OCR 입력이나 ROI 설정에 넣지 않는다.

| 기록 단위 | 남길 내용 |
| --- | --- |
| 실행 조건 | 코드 커밋(`git rev-parse HEAD`), 카메라/태블릿, 실제 해상도, 거리/배치/밝기/초점, ROI 설정, 스트림 인자 |
| 시나리오 | 수동 정답 ALT/HDG/IAS, 변경 또는 가림/분리 시점, 반복 횟수 |
| 관측 | 실행 UUID·프레임 ID, 호스트 수신 시각, value·candidate_value·reason·stable_count, health, 근거 파일 경로 |
| 평가 | 정답 일치/오인식/보류, 안정화까지의 관측 지연, 장애 때 이전 값 제거 여부, 복구 후 재안정화 여부 |

호스트 수신 시각으로 센서 노출 지연을 측정했다고 표현하지 않는다. 결과 수와 실패 사례를 함께 보고하며 모델 점수를 검증된 정확도로 바꾸지 않는다. 현재 WI 상태와 최신 결과는 [TODO](../../docs/spec/todo.md)와 [workitem 기록](../../docs/spec/003-cockpit-vision.md)을 따른다.
