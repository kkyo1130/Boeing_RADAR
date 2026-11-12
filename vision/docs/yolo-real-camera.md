# 실제 카메라 YOLO11n MCP 탐지 개선

2026-11-12 사용자 요청. 상태 verifying: 코드/fixture 검증과 실제 성능 개선을 구분한다. CNN v5/v6, 정답 수집 ACK, React/3D 디자인 및 기존 가중치는 유지한다. 신규 모델은 명시적인 --yolo-weights로 선택하며 자동 교체하지 않는다.

## 기존 모델 분석

실제 발견한 학습 출력은 형제 Boeing_RADAR 프로젝트의 `runs/detect/vision/checkpoints/mcp_yolo/baseline_v7`이다. 해당 args.yaml은 Boeing_RADAR-vision의 mcp_blender_v7/dataset_local.yaml을 가리킨다. 현재 웹캠 프로세스에서 어떤 가중치를 사용했는지는 여기서 확정하지 않았다.

- 학습: YOLO11n, 30 epoch, imgsz960, batch4, device MPS, optimizer auto, lr0 .01, seed0, mosaic1, fliplr .5.
- 합성 mcp_blender_v7: 18장, 6세션, train12/val3/test3. 실제 데이터 전무. manifest와 박스 형식 검증 통과.
- results.csv 마지막(epoch30): Precision .57977 / Recall .66667 / mAP50 .65400 / mAP50-95 .25649.
- mAP50-95 최대 기록도 .25649(epoch27부터); 이는 기록의 지표 기준이며 best.pt 선택 epoch를 별도 확인한 것은 아니다. 실제 테스트셋 결과가 아니다.
- 원인 가설: 매우 작은 합성 데이터와 실물의 촬영 거리·시점·노출·픽셀/모아레·반사 차이. 이것이 0.41의 직접 원인이라고 확정할 수 없다. 0.41은 모델 점수이며 정확도/검증된 확률이 아니다.
- 다음 학습은 기존 best.pt 초기화, 합성 split 보존 + 실제 train/val 추가, AdamW lr0 .0005, fliplr/flipud0, mosaic .3, degrees8, perspective .0003, 명암 변형을 사용한다. 하이퍼파라미터는 시작 설정이고 개선 보장이 아니다. 테스트셋으로 튜닝하지 않는다.

## 실제 이미지 수집과 수동 박스

프로젝트 루트에서 기존 torch/cv2/Pillow/ultralytics 가상환경의 python을 사용한다. 로컬 검증은 형제 프로젝트 .venv/bin/python과 설치된 ultralytics8.4.209에서 수행한다.
태블릿에서 기존 3D Cockpit을 켠다. detector 정답은 MCP 패널 전체 박스로 사람이 지정하고 CNN 숫자 정답과 별개다.

권장190장: train 3세션×40장 + val 별도30장 + test 별도40장.

```sh
python vision/collect_yolo_camera.py --source 0 --output vision/data/yolo_camera/train_near --session yolo_train_near_01 --split train --count 40 --condition near_front_varied_light
python vision/collect_yolo_camera.py --source 0 --output vision/data/yolo_camera/train_far --session yolo_train_far_01 --split train --count 40 --condition far_front_varied_light
python vision/collect_yolo_camera.py --source 0 --output vision/data/yolo_camera/train_angle --session yolo_train_angle_01 --split train --count 40 --condition left_right_up_down_reflection
python vision/collect_yolo_camera.py --source 0 --output vision/data/yolo_camera/val --session yolo_val_day2_01 --split val --count 30 --condition independent_varied_conditions
python vision/collect_yolo_camera.py --source 0 --output vision/data/yolo_camera/test --session yolo_test_day3_01 --split test --count 40 --condition unused_independent_varied_conditions
```

세션 사이 촬영을 종료하고 위치/환경을 바꾼다. 한 세션을 다른 ID로 바꿔 train/test에 나누지 않는다. ID는 실제 촬영 세션 식별자이며 프로그램이 물리적 세션 차이를 증명하지는 못한다.
각 세션에서 가까움/멀리, 좌우/상하 비스듬함, 밝고 어두운 조명, 태블릿 밝기/반사를 골고루 포함한다. 빛 반사로 MCP 전체가 식별되지 않으면 잘못 라벨하지 말고 건너뛴다.
SPACE로 원본 프레임을 고정하고 MCP 외곽 전체(숫자 창과 조작부 포함, 주변 EFIS/주 계기 제외)를 드래그 → Enter/Space로 확정. C로 취소한다. N은 조건 메모 변경, Q/Esc 종료. 최소2초 간격이며 움직임 없는 중복 프레임은 거절한다.
기존 출력 폴더는 덮어쓰지 않는다. 이미지·정규화 YOLO class0 bbox·세션/split/조건 manifest.csv와 collection.json을 저장한다. detector 예측으로 자동 정답을 만들지 않는다.

## 혼합 학습

기존 모델 위치를 환경 변수로 지정한다. 셸 경로는 아래 실제 발견 경로이며 프로젝트 루트 기준이다.

```sh
YOLO_BASE=../Boeing_RADAR/runs/detect/vision/checkpoints/mcp_yolo/baseline_v7/weights/best.pt
python vision/finetune_yolo_camera.py \
  --synthetic vision/data/mcp_blender_v7 \
  --camera vision/data/yolo_camera/train_near \
  --camera vision/data/yolo_camera/train_far \
  --camera vision/data/yolo_camera/train_angle \
  --camera vision/data/yolo_camera/val \
  --real-test vision/data/yolo_camera/test \
  --init "$YOLO_BASE" --output vision/checkpoints/mcp_yolo_real_v1 \
  --epochs 40 --imgsz 960 --batch 4 --device mps
```

--prepare-only는 검증과 병합만 한다. 출력이 생성되므로 실제 학습은 새로운 output을 사용한다.
새 best 경로는 `vision/checkpoints/mcp_yolo_real_v1/fit/weights/best.pt`이다. 합성 train/val/test 구분은 그대로이며 실제 test는 mixed 데이터에 복사하지 않는다. 학습은 val로만 선택하고 카메라 test는 평가하지 않는다.
원본 이미지·라벨·가중치는 수정하지 않는다. 기존 output 또는 입력과 겹치는 경로는 실패한다. training_manifest.json에 데이터 fingerprint와 고정 heldout fingerprint를 기록한다.

## 동일 미사용 실물 테스트셋 비교

```sh
python vision/compare_yolo_camera.py \
  --test vision/data/yolo_camera/test \
  --old "$YOLO_BASE" \
  --new vision/checkpoints/mcp_yolo_real_v1/fit/weights/best.pt \
  --seen vision/data/mcp_blender_v7 \
  --seen vision/data/yolo_camera/train_near \
  --seen vision/data/yolo_camera/train_far \
  --seen vision/data/yolo_camera/train_angle \
  --seen vision/data/yolo_camera/val \
  --output vision/reports/yolo_real_compare_01 --imgsz 960 --device mps
```

동일 해상도/동일 이미지/동일 평가 설정으로 Precision, Recall, mAP50, mAP50-95와 차이를 comparison.json에 기록한다. AP 측정용 conf .001과 실제 CNN 전달 정책 .5는 구분한다.
boxes.json은 각 이미지의 정답/최상위 예측 좌표·점수·IoU·정책 수용 여부/사유를 담는다. mean top1 IoU, IoU≥.5/.75 비율, 공간 게이트 수용률과 수용된 박스 IoU도 보고한다. `old/overlays`, `new/overlays`의 정답 녹색/예측 빨간색 박스를 실제로 검토한다. MCP 가장자리·숫자창/조작부가 잘려 있지 않은지 확인한다.
테스트 복사본을 output/test_data에 만들어 Ultralytics cache가 원본 테스트 폴더를 수정하지 않게 한다. 알려진 학습 manifest와 --seen 데이터에 대해 세션·픽셀 중복을 확인하고 평가 중 테스트 변경을 거절한다.
최종 결과를 보고 재학습했다면 해당 test는 더 이상 미사용이 아니다. 새로운 물리 세션을 남겨 다음 평가에 사용한다. 단일 패널 양성 이미지 평가이므로 MCP 없는 장면의 오탐 성능과 시간 안정성은 별도 영상 평가가 필요하다.

## OCR 연결과 실패 처리

새 모델을 실제 테스트와 박스 오버레이에서 검토한 후 명시적으로 선택한다.

```sh
python vision/live_mcp_ocr.py --source 0 --checkpoints vision/checkpoints/mcp_ocr_v5 \
  --yolo-weights vision/checkpoints/mcp_yolo_real_v1/fit/weights/best.pt --yolo-conf 0.5 --yolo-imgsz 960 --yolo-stable-frames 3
python vision/collect_camera_mcp.py --source 0 --display-id tablet --preset-plan --auto-interval 0 \
  --output vision/data/camera_batches/new_yolo_verified \
  --yolo-weights vision/checkpoints/mcp_yolo_real_v1/fit/weights/best.pt --yolo-conf 0.5 --yolo-imgsz 960 --yolo-stable-frames 3
```

CNN v6는 공식 학습/검증 후 --checkpoints에 해당 폴더를 직접 지정한다. 기존 v5/v6 명령과 ACK는 유지한다.
YOLO 선택 시 기본 score≥.5, 최근3프레임 panel IoU≥.8, class0, 화면 가장자리 잘림/극단 크기 거부, 유력한 별도 패널 후보 거부, 내부 HDG/ALT 모두 검출·범위 검증을 요구한다. 기준은 보수적 시작 정책이며 확률 보정이나 정확도 보장이 아니다. 최대.41인 기존 모델은 기본 정책에서 보류된다. threshold는 val에서 평가해 조정하고 test로 튜닝하지 않는다.
실패 시 전체프레임 OpenCV로 자동 우회하지 않고 CNN 입력/숫자 저장을 막는다. live는 이전 ROI와 숫자 안정화 이력을 비우고 원본 무주석 프레임만 CNN으로 전달한다. 사용자 H/A 수동 ROI 선택은 명시적인 수동 모드로 유지된다. YOLO 미선택 시 기존 OpenCV 동작을 유지한다.

## 구현·검증·리뷰·인수인계

추가: collect_yolo_camera.py, yolo_camera_data.py, finetune_yolo_camera.py, compare_yolo_camera.py, mcp_yolo_gate.py, test_yolo_camera_pipeline.py, 본 문서.
수정: live_mcp_ocr.py, collect_camera_mcp.py 및 TODO. 기존 사용자의 미커밋 CNN/ACK 변경은 보존했다.

검증:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=vision:. python -m pytest \
  vision/test_yolo_camera_pipeline.py vision/test_v6_pipeline.py vision/test_mcp_display_sync.py vision/tests \
  -q -p no:cacheprovider --basetemp=/tmp/radar-yolo-real-regression
```

자체 리뷰: label 경계·NaN/손상/누락/중복/경로 탈출, 세션 누수와 입력 덮어쓰기, 테스트셋 학습 유입, 낮은 점수/복수 후보/박스 이탈/장치 실패 후 CNN 차단, 오래된 ROI·화면 주석의 CNN 유입을 검토했다. 외부 리뷰/PR 제출은 미실행이고 사용자 브랜치의 미커밋 변경이다.
실제 Mac 카메라 GUI 수집, 실제190장 라벨, MPS 공식 학습, 실제 미사용 테스트에서 성능/오버레이 개선, 연속 영상에서 gate 동작은 미실행이다. 코드 구현을 실제 성능 개선 완료로 표현하지 않는다.

### 이번 실행 결과

- 기존 CNN/ACK/vision 회귀와 신규 YOLO를 함께 실행: 76 passed. 이후 추가된 비교 보고서 테스트까지 신규 YOLO 9 passed (중복 제외 총77사례).
- 실제 수집 GUI는 모의 OpenCV로 검증: SPACE→수동 박스→2장 저장→정규화 좌표 복원/고정 session·test split 확인.
- detector gate: .41 점수 보류, 다른 패널 후보·잘린 박스 거부, 3프레임 안정화, 이동/실패 시 초기화, 내부 숫자 창이 둘 다 없으면 CNN 전달 없음. 일반 COCO class0 person 가중치 사용 차단.
- 신규 비교 도구 모의 지표/박스 검증: 동일 테스트셋 유지, 모델별 Precision/Recall/mAP와 IoU·Pillow 오버레이 생성 및 fingerprint 불변 확인.
- 실제 ultralytics8.4.209 + torch2.15 CPU smoke: 기존 baseline_v7 best.pt 초기화 → 작은 가짜 단색 fixture 1epoch → 새 best.pt → 실제 양 모델 .val/.predict → comparison.json/boxes.json/overlays 생성까지 성공. 성능 수치는 의미 없는 fixture 값이며 실물 성능 개선 근거로 사용하지 않는다.
- 검증 산출물은 임시 radar-yolo-smoke 폴더에만 저장했고 기존 모델·원본 데이터는 보존했다. 공식 mcp_yolo_real_v1 학습은 미실행.
- 초기 macOS 폰트 검색이 지연됐고 진단 timeout의 native stack dump 중 exit139가 발생했다. 새 도구에 Agg backend/자동 plots=False를 적용하고 진단 타이머를 제거한 재실행은 정상 완료했다. 원인 확정은 하지 않는다. 직접 생성하는 Pillow 박스 오버레이는 유지한다. 임시 폰트/캐시만 사용했다.
- 기존 합성18장 manifest/박스 검증, Python 구문과 git diff --check 통과.
- 자동 플롯을 끄므로 Ultralytics의 PR곡선 이미지는 제공하지 않지만 요청한 수치 지표와 박스 오버레이는 저장한다.

## 2026-11-12 자동 촬영·반자동 라벨링 추가

--auto-interval 2와 기존 MCP 가중치로 미검증 후보/검토 대상을 수집하고, 모든 이미지를 사람이 확인/드래그 수정한 뒤 별도 확정 폴더로 내보낼 수 있다. 높은 모델 점수만으로 정답을 확정하지 않으며 미검증 원본은 학습에서 차단한다. [자동 수집·전수 검토 명령과 검증](yolo-auto-capture.md)을 따른다. 기존 수동 명령과 세션 분리는 유지한다.

## 같은40장 IoU·게이트 진단

기존 top-1 IoU와 AP/게이트는 서로 다른 지표이며 테스트 라벨은 기존 모델 제안의 수정 없는 승인40장이다. [게이트·라벨 편향·전처리 차이 분석과 재평가 결과](yolo-gate-diagnosis.md)를 확인한다. 실제값 전체/탐지 평균과 원인별 시각화는 reports/yolo_real_compare_03_diagnostics에 저장했다. 임계값은 낮추지 않았다.
