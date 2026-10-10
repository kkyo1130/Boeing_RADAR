# Vision: 정지 이미지와 태블릿 촬영 스트림

정지 이미지에서 **선택 ALT·HDG**를 읽고 설정에 따라 MCP 속도를 추가로 관측한다. 태블릿용 화면은 frontend에 있다. 웹캠·영상 파일 입력, 연결/지연 감시와 연속 판독 안정화를 추가했으며 실제 태블릿/카메라의 ROI·촬영 조건 검증은 남아 있다. 포함한 화면은 직접 생성한 합성 fixture로 실제 계기 판독 성능을 대표하지 않는다.

태블릿 화면 → 촬영 프레임 저장 → ROI 설정 → 스트림 실행은 [태블릿 데모 안내](docs/tablet-demo.md)를 따른다.

## 실행 (저장소 루트)

Python 3.11 이상, macOS Command Line Tools가 필요하다. Python은 입력·ROI·결과 처리를 담당하며 초기 OCR 어댑터는 macOS Vision이다. 다른 OS의 OCR 엔진은 아직 제공하지 않는다.

```sh
python3 -m venv vision/.venv
vision/.venv/bin/python -m pip install -e './vision[test]'
mkdir -p vision/.build
xcrun swiftc vision/native/ocr.swift -o vision/.build/radar-ocr
vision/.venv/bin/radar-vision vision/evaluation/fixtures/normal.png --config vision/configs/synthetic.json --ocr-binary vision/.build/radar-ocr --output-dir vision/output
vision/.venv/bin/python -m pytest vision/tests -q
vision/.venv/bin/python vision/evaluation/run.py --ocr-binary vision/.build/radar-ocr
```

OCR에 macOS 실행 권한이 필요할 수 있다. OCR 실행 실패는 `ocr_unavailable`로 기록한다. 실제 엔진 검증은 별도 evaluation 명령으로 수행한다. 스트림 안전 경계 테스트는 결정론적 OCR 실행 파일과 가짜 카메라를 사용하므로 실제 모델/장비 검증과 구분한다.

## 실제 화면으로 전환

1. 선택 고도와 선택 방위가 표시된 화면의 이미지 확보. 현재 고도/QNH는 읽지 않는다.
2. `configs/synthetic.json`을 별도 설정 파일로 복사한다.
3. `image_size`를 실제 픽셀 크기로, 각 `roi`를 `[left, top, right, bottom]`으로 지정한다. 원점은 좌상단, 오른쪽/아래 경계는 제외한다. 자동 크기 변경은 하지 않는다.
4. ALT 표기가 feet 숫자면 `feet`, FL 숫자면 `FL`로 지정한다. 단위 글자는 ROI에서 제외한다. HDG는 `degrees`이며 360을 임의로 0으로 바꾸지 않는다.
5. 정상·설정 변경·가림·흐림·반사 샘플과 수동 정답을 따로 수집한다. 실제 영상은 사용 권한을 확인하고 무조건 Git에 추가하지 않는다.
6. CLI로 실제 촬영 이미지를 검증한 뒤 스트림을 실행한다. [태블릿 데모 안내](docs/tablet-demo.md)를 참고한다.

결과와 전체 이미지·ROI 근거는 출력 폴더의 프레임별 하위 폴더에 저장한다. 라벨은 evaluation에서만 사용한다. 모델 점수는 정확도/확률이 아니며 `minimum_model_score=0.5`는 실험 설정이다. 빈 영역·문자 혼입·낮은 점수·OCR 장애는 숫자 대신 null과 사유를 반환한다. 흐림/반사 일반 탐지는 아직 없으며, 읽힌 오답을 모두 걸러낸다는 보장은 없다.

파일의 실제 촬영 시각을 알 때만 `--captured-at 2026-10-10T06:00:00Z`를 지정한다. 생략하면 촬영 시각은 null이다. 처리 시각이나 파일 수정 시각을 촬영 시각으로 쓰지 않는다. 서버 최종 판정은 이 PoC가 하지 않는다.

## 결과 JSON 확인

`observation.json`의 전체/필드별 항목, 단위, ROI 좌표, 실패 사유와 해석상 주의점은 [결과 JSON 설명](../contracts/vision-poc.md)에 정리했다. 종료 코드 0은 처리가 끝났다는 의미이며 모든 숫자 판독 성공을 뜻하지 않는다.

## 현재 범위

- 구현: 이미지·영상·웹캠 입력, 수동 ROI 설정, ROI 근거, OCR, FL→feet, 0도, 실패/범위 검사, 끊김·지연 감시, 연속 판독 안정화, 로컬 JSON 결과.
- 미완료: 흐림/반사 일반 탐지, 서버 전송·지시 연결, 실제 태블릿 카메라 검증. 실제 Cockpit 검증은 이번 데모 범위 밖이다.
- 결과 형식과 현재 서버의 차이: [계약 초안](../contracts/vision-poc.md).
- 현재 검증 근거: [평가 기록](evaluation/README.md).

OCR API 근거: [Apple VNRecognizeTextRequest](https://developer.apple.com/documentation/vision/vnrecognizetextrequest). 최종 엔진 선택은 실제 화면 평가 후 결정한다.

## Cockpit 참고 화면 설정

사용자가 제공한 참고 사진에는 중앙 위에 HEADING·ALTITUDE 숫자 창이 있다. 해당 1448×1086 이미지 전용 설정은 `configs/cockpit-reference.json`이다. 숫자 창에서 ALT 10000ft, HDG 272°를 읽은 결과는 [평가 기록](evaluation/README.md)에 남겼다. 첫 번째 참고 사진은 저장소에 포함하지 않았으므로 실행할 때 해당 이미지 경로를 입력한다. 최신 MCP 참고 사진은 [팀 공유 문서](../docs/vision/README.md)에 포함했다.

```sh
vision/.venv/bin/radar-vision /path/to/cockpit.png --config vision/configs/cockpit-reference.json --ocr-binary vision/.build/radar-ocr --output-dir vision/output/reference
```

실제 촬영에서는 두 창의 숫자가 충분히 크게 보이도록 카메라 위치·초점·해상도를 정하고 ROI를 다시 맞춘다. 위 설정은 전체 화면/패널 자동 탐지나 카메라 흔들림 보정 기능이 아니다.

## 고정 카메라 배치

두 조종석 사이 뒤쪽의 고정 지지대에서 MCP 세 표시창을 촬영하는 [배치 기준](docs/camera-setup.md)을 반영했다. 새 참고 사진용 설정은 `configs/mcp-fixed-camera.json`이다. 속도 관측은 선택 기능이며 기존 두 필드 설정도 그대로 실행된다.

```sh
vision/.venv/bin/radar-vision /path/to/mcp.png --config vision/configs/mcp-fixed-camera.json --ocr-binary vision/.build/radar-ocr --output-dir vision/output/mcp-fixed
```

## 작은 방위 창 전처리

MCP 설정의 `heading.ocr_preprocessing`으로 방위 ROI만 흑백·4배 확대하여 OCR에 넣는다. 같은 사진에서 HDG 270/ALT 10000/speed 250을 확인했다. 원본 `heading.png`와 전처리된 `heading-ocr.png`를 함께 저장하므로 [결과 JSON](../contracts/vision-poc.md)에서 처리 근거를 확인할 수 있다. 다른 창/촬영 조건에 같은 전처리가 항상 유리한 것은 아니다.

## 팀 공유 결과

사진·실제 결과 JSON·ROI/OCR 근거 및 재현 명령은 [MCP Vision PoC 문서](../docs/vision/README.md)에 모았다. 중간 output은 정리했고 필요하면 재실행한다.

## 스트림 결과

`vision-stream/1`은 로컬 이벤트 형식이다. `observation` 이벤트는 vision-stream-observation/1 결과를 담고, `health` 이벤트는 `observation=null`로 이전 숫자를 제거한다. 현재 서버의 공통 계약이나 최종 판정이 아니다.

- `event_type`: observation 또는 health.
- `input_mode`: camera 또는 video_file. `live_input`은 카메라 경로 여부이며 정상/신선함을 보증하지 않는다.
- `health`: 입력 상태 available/degraded/unavailable와 reason. OCR 실패는 필드 reason으로 따로 남긴다.
- `emitted_at`: UTC 이벤트 생성 시각. 카메라 `frame_age_seconds`는 호스트 수신부터 OCR 완료까지의 시간이다. 파일에서는 null.
- `observation`: schema_version=vision-stream-observation/1. ocr_schema_version은 원래 정지 이미지 OCR 버전(/1 또는 /2)을 기록한다. frame_sequence, capture_time_basis(host_receive/unknown), media_time_ms와 기존 값·시각·근거. 카메라의 captured_at은 호스트 수신 시각이며 센서 노출 시각이 아니다. 파일의 captured_at은 null.
- `stable_count`: 연속 같은 값 판독 횟수. `candidate_value`는 진단용으로, 안정화 전에도 존재할 수 있다. 소비자는 value와 reason을 사용해야 한다.
- `latest.json`: 마지막 이벤트를 원자적으로 교체한다. health일 때 지난 observation을 재사용하지 않는다. 오래된 파일 자체를 새 입력으로 해석하지 않는다.

상태 사유: camera_starting/camera_unavailable/camera_disconnected/camera_error/frame_timeout/stale_frame/stale_observation/camera_reconnected/capture_stopped/input_error/video_ended/video_no_frames/playback_stopped. 필드 reason은 기존 OCR 사유와 unstable_reading 또는 입력 장애 사유다. 별도 감시 스레드가 OCR 처리 중에도 이전 관측 만료/프레임 중단을 감시한다.

입력/설정 오류는 종료 코드 2, 정상 종료 및 Ctrl-C는 0이다. 종료 코드 0은 숫자 판독 성공을 뜻하지 않는다. Ctrl-C는 진행 중인 네이티브 OCR 호출 종료까지 지연될 수 있으며, 그동안 상태 감시는 계속된다. 카메라 장애 시 수신을 재시도하므로 카메라 모드는 duration 또는 Ctrl-C까지 실행된다.
