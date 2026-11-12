# YOLO 실제 카메라 자동 촬영과 전수 검토

2026-11-12 사용자 추가 요청. 자동 촬영은 학습 정답을 확정하지 않는다. 기존 수동 SPACE→박스→Enter, CNN v5/v6, Python–React ACK와 3D 디자인은 유지한다.

## 자동 수집

프로젝트 루트에서 cv2/Pillow/numpy/ultralytics가 설치된 가상환경 Python을 사용한다. 이 체크아웃에 .venv가 없어 검증은 `../Boeing_RADAR/.venv/bin/python`으로 실행했다. 아래 python은 사용 중인 가상환경 실행 파일을 뜻한다.

```sh
YOLO_BASE=../Boeing_RADAR/runs/detect/vision/checkpoints/mcp_yolo/baseline_v7/weights/best.pt
python vision/collect_yolo_camera.py \
  --source 0 \
  --output vision/data/yolo_camera/auto_train_near_01 \
  --session yolo_train_near_auto_01 --split train --count 100 \
  --auto-interval 2 --yolo-weights "$YOLO_BASE" \
  --yolo-device mps --yolo-imgsz 960 --yolo-conf 0.5 --yolo-stable-frames 3
```

태블릿의 전체 MCP가 보이도록 각도·거리·화면 밝기·조명·반사를 바꾼다. 첫 타이머 촬영은 시작2초 이후이며 추론/파일 저장이 느리면 실제 간격은 더 길 수 있다. 자동 모드에서는 박스 드래그나 Enter 없이 수집한다.

화면: 자동 촬영 간격, 저장 수/목표, 미검증 전체 수, 안정 후보 수, 검토 필요 수, 중복 제외 수, 현재 모델 점수/판정 사유와 예측 박스. 초록 박스도 정답 확정이 아니라 안정 후보이다. 주황 박스는 검토 대상이다. 모델 점수는 보정된 정확도가 아니다.

- `candidates/`: 모델 score≥설정값, 연속 설정 프레임(기본3) IoU≥.8, 박스 크기/경계/복수 후보 검사에 통과한 미검증 제안.
- `needs_review/`: 낮은 점수/불안정/복수 후보/잘림/미검출/추론 오류 이미지. 제안 가능한 박스는 참고 좌표로만 저장한다. 실패한 이미지는 버리지 않는다.
- `capture_manifest.json`: 원본 이미지 경로/픽셀 hash/세션/split/시간/조건/모델 점수/사유/제안 좌표. 모두 PENDING.
- `collection.json`: 원본 모델 경로/hash, 기준값, 목표/저장 수, TARGET_REACHED/USER_QUIT/CAMERA_READ_FAILED 및 완료 여부. 촬영 시각은 카메라 read 완료 시각이며 장치 하드웨어 시각 보장은 아니다.
- 자동 폴더에는 YOLO .txt label이나 dataset.yaml/학습 manifest를 만들지 않는다. 기존 데이터 로더가 직접 학습 사용을 차단한다.

저장 수(안정 후보+검토 필요)가 --count에 도달하면 자동 종료한다. 중복 프레임은 수량에 포함하지 않는다. 같은 장면을 유지하면 목표 수량에 도달하지 않을 수 있으므로 실제 촬영 조건을 바꾼다. Q/Esc로 조기 종료 가능, SPACE는 타이머 외 즉시 시도, N은 조건 메모 변경이다. 조기 종료/카메라 실패의 기존 저장분도 검토할 수 있지만 목표 달성으로 표시하지 않는다.

--dedup-distance 기본 .015: 최근20개 저장 이미지의 64×48 RGB thumbnail 평균 절대 차이와 전체 픽셀 hash로 근접/동일 프레임을 제외한다. 유용한 차이도 너무 많이 제외하면 .005 등으로 낮추되 실제 이미지로 확인한다. 이것은 근접 중복 휴리스틱이며 세션 분리를 대신하지 않는다. 저장되지 않은 중복은 새 기준 프레임으로 추가하지 않는다.

train/val/test는 전체 물리 촬영 세션 단위로 고정한다. val/test 수집은 새 세션·새 폴더에서 --split val 또는 test와 새 --session을 사용한다. 한 연속 세션을 ID만 달리해 train/test에 나누지 않는다. 모든 세션에서 카메라 조건을 다양화한다.

## 모든 라벨 검토와 수정

```sh
python vision/review_yolo_camera.py \
  --input vision/data/yolo_camera/auto_train_near_01 \
  --output vision/data/yolo_camera/reviewed_train_near_01
```

안정 후보와 실패 이미지를 포함한 **전체** 이미지가 한 장씩 표시된다.

- Enter/SPACE: 현재 표시한 박스를 사람이 확인하고 승인한다. 박스가 없는 미검출 이미지는 승인할 수 없다.
- R: 원본 이미지에서 마우스 드래그로 MCP 전체 외곽을 다시 지정 → Enter/SPACE. 반환된 박스를 확인하고 다시 Enter/SPACE로 승인한다.
- D: 사용할 수 없는 이미지를 제외한다. 원본 이미지는 삭제하지 않고 거절 이력을 남긴다.
- Q/Esc: reviews.json에 진행 상황을 저장하고 종료한다. 같은 명령으로 미검토 항목부터 재개한다.

한 장이라도 미검토이면 학습 데이터셋을 내보내지 않는다. 모두 승인/거절한 뒤에만 별도 output의 images/<split>, labels/<split>, manifest.csv, dataset.yaml과 review_audit.json을 생성한다. 승인된 이미지만 포함하며 기존 세션/split을 유지한다. 전부 거절하면 학습 데이터셋은 만들지 않는다.

`--export-only`는 이미 끝낸 검토를 내보낼 뿐 미검토를 자동 승인하지 않는다. 원본 이미지/manifest가 바뀌면 진행을 재사용하지 않는다. 미완료 파일이나 경로 탈출/중복 ID/잘못된 박스도 거절한다.
학습 직전에 승인 이력의 이미지 hash·박스·세션·split·수량과 실제 학습 파일을 다시 대조한다. 승인 후 label/image가 달라졌거나 audit가 없으면 학습이 차단된다. 사람이 잘못 승인한 박스 자체의 정확도를 소프트웨어가 보장하는 것은 아니다. 특히 test는 모델 제안을 그대로 신뢰하지 말고 원본 패널 전체를 독립적으로 확인한다.

## 학습에 연결

기존 finetune_yolo_camera.py의 --camera에는 **reviewed_... 폴더만** 지정한다. test도 별도 세션에서 전체 검토한 폴더를 --real-test에 지정한다. 자동 수집 원본 폴더를 넘기면 UNVERIFIED 오류로 차단한다. 합성·실제 혼합과 기존 train/test 세션/픽셀 중복 검증은 그대로다. 자세한 학습/평가 명령은 [기존 YOLO 안내](yolo-real-camera.md)를 따른다.

## 기존 수동 수집

```sh
python vision/collect_yolo_camera.py --source 0 \
  --output vision/data/yolo_camera/manual_train_02 \
  --session yolo_manual_train_02 --split train --count 40
```

--auto-interval 생략 또는0이면 기존 SPACE→MCP 전체 드래그→Enter와 최소 촬영 간격을 유지한다. 기존 수동 모드의 정확 중복 검사는 유지하고 근접 thumbnail 중복 제거는 자동 모드에만 적용한다.
기존 폴더를 덮어쓰거나 임의 삭제하지 않는다. 예시 이름이 있으면 새 이름을 사용한다.

## 구현·검증·리뷰·인수인계

수정: collect_yolo_camera.py (자동 CLI 분기, 수동 유지), yolo_camera_data.py (미검증/승인 이력 학습 차단), train_mcp_yolo.py (기존 학습 진입점에도 동일 검사).
추가: yolo_auto_collection.py (타이머/탐지/중복/진행), review_yolo_camera.py (전수 GUI 검토·수정·확정 export), test_yolo_auto_collection.py와 본 문서. TODO/기존 YOLO 안내에 연결했다. CNN/ACK/React/3D 코드와 가중치는 이번 요청에서 수정하지 않았다.

검증 명령:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=vision:. python -m pytest \
  vision/test_yolo_auto_collection.py vision/test_yolo_camera_pipeline.py \
  vision/test_v6_pipeline.py vision/test_mcp_display_sync.py vision/tests \
  -q -p no:cacheprovider --basetemp=/tmp/radar-auto-yolo-final-tests
```

자동 수집은 카메라/시계/OpenCV UI/모델 출력 mock으로 검증했다. 2초 간격 시도, 중복 제외, 목표 수에서 read 중단, stable/low/no detection/error 분리, 원본 모델 불변, 미검증 학습 차단, Enter/드래그/거절/중단·재개, 부분 검토 export 차단, 검토 후 라벨/이미지/audit 변경 거부, 세션 누수/경로 탈출을 확인한다.
별도로 실제 기존 baseline_v7 weights를 CPU로 불러와 실제 합성 입력3회 predict_candidate를 실행했다. 높은 점수(.99758)여도 복수 패널 모호성으로 needs_review에 남았고 원본 weights hash는 불변이었다. 실제 카메라 성능 결과가 아니다.

자체 리뷰: 자동 경로는 확정 label을 생성하지 않으며 높고 안정된 score도 사람의 승인을 우회하지 않는다. 미검출의 잘못된 좌표/이전 박스를 새 정답으로 채우지 않는다. 모델 오류도 review로 남긴다. 원본 프레임과 화면 주석을 분리하고 export는 승인된 원본만 복사한다. 새 출력 경로/atomic JSON/픽셀 hash/검토 audit를 확인했다. 외부 리뷰는 미실행.
남은 확인: 실제 Mac 카메라 접근·MPS 처리속도·마우스 GUI와 실제100장 수집은 미실행이다. 중복 거리/score 기준은 실물 조건에 따라 검증해야 한다. 새 모델 학습/기본 모델 변경은 이번 범위가 아니다. 사용자 브랜치의 미커밋 변경이며 커밋/PR은 생성하지 않았다.

### 최종 실행 결과

- 기존 vision/CNN v6/ACK/YOLO와 신규 자동 수집·검토를 함께 실행: **89 passed**, skip 없음.
- 신규 자동 수집·검토 테스트12개: 타이머/목표 종료/중복/실패 분리/전수 승인/드래그 수정/거절/중단·재개/원본 변조/승인 후 파일 변경/박스 없는 이미지 승인 차단/경로 탈출/기존 학습 진입점 차단 포함.
- 실제 baseline_v7 모델의 합성 이미지3회 추론 성공, 원본 가중치 SHA256 불변. 높은 .99758 점수도 복수 후보 모호성으로 needs_review로 분류되는 것을 확인했다.
- 기존 합성 데이터의 train12/val3/test3 검증 통과. CLI help/Python 구문/git diff --check 통과.
- 실제 카메라 촬영·OS 카메라 권한·MPS 속도·실제 마우스 GUI 조작은 미실행. GUI/카메라 흐름은 모의 입력으로 검증했다.
