# CNN v6 카메라 파인튜닝 파이프라인

2026-11-12 사용자 요청 추가 범위. 상태: verifying. 실제 새 카메라 데이터 160+40쌍은 아직 수집하지 않았고 공식 v6 학습/실물 비교도 미실행이다. 기존 v5, 합성 데이터, React 디자인/ACK 구현과 기본 OCR v3 경로는 유지한다. 이 문서는 이번 범위의 구현·검증·리뷰·인수인계 원본이다.

## 수집

프로젝트 루트에서 가상환경 Python을 사용한다. 이 체크아웃에는 .venv가 없으므로 검증은 `../Boeing_RADAR/.venv/bin/python`을 사용했다. 아래 `python`은 torch/cv2/Pillow/ultralytics가 설치된 환경의 실행 파일을 뜻한다.

Frontend: `cd frontend && npm run dev`. 태블릿: `http://<Mac LAN IP>:5173/cockpit?display=tablet`.
카메라가 촬영하는 브라우저 하나만 display=tablet으로 설정하고 탭을 전면에 둔다.

학습 세션에서 실행:

```sh
python vision/collect_camera_mcp.py \
  --source 0 --display-id tablet --auto-interval 0 \
  --v6-plan train --session-id v6_train_session_01 \
  --output vision/data/camera_batches/v6_train_160
```

종료 후 별도 촬영 세션을 시작하고 카메라 위치/각도/거리나 조명 조건을 바꿔 테스트를 수집한다. 같은 연속 녹화에서 프레임만 나누지 않는다. 실제 물리 세션 구분은 운영자가 지켜야 하며 소프트웨어는 입력한 세션 ID와 데이터 중복을 검증한다.

```sh
python vision/collect_camera_mcp.py \
  --source 0 --display-id tablet --auto-interval 0 \
  --v6-plan test --session-id v6_test_session_01 \
  --output vision/data/camera_batches/v6_test_40
```

학습 123/04500,287/13700,054/21000,349/07800,201/15400,308/06300,076/19800,195/32700;
테스트 032/00600,264/28400. 각각 20쌍. train/test는 각각 별도 폴더의 train/test split에 기록한다.
READY 후 SPACE로 저장. 20쌍마다 저장 차단 후 N→Enter로 다음 조합. N→R 재동기화, Q 종료.
일반 수동 입력 N→M, 기존 --preset-plan의 8조합×15쌍, 자동 촬영 --auto-interval 0.6은 유지한다.
학습된 YOLO 탐지는 기존 `--yolo-weights <best.pt>` 옵션을 추가한다.
`collection.json`을 삭제하거나 재작성하지 않는다. 세션 ID/계획이 달라지면 같은 폴더에 재개할 수 없다.
새 폴더 이름이 이미 존재하면 덮어쓰지 말고 새 이름을 사용한다. 중단 파일이 CSV에 반영되지 않았으면 수집기가 덮어쓰기를 차단한다.

## v6 학습

기존 120쌍 확인 위치: `vision/data/camera_batches/sync_test_20261112_021206` (240행, 검증 통과).
합성 base는 `vision/data/mcp_ocr_aligned`이다. 이미 카메라 데이터가 합쳐진 v5/merged_training_data를 base로 쓰고 동일 카메라를 다시 추가하지 않는다. 중복 검사가 이를 차단한다.

```sh
python vision/finetune_camera_mcp.py \
  --v6 --base vision/data/mcp_ocr_aligned \
  --camera vision/data/camera_batches/sync_test_20261112_021206 \
  --camera vision/data/camera_batches/v6_train_160 \
  --real-test vision/data/camera_batches/v6_test_40 \
  --init-checkpoints vision/checkpoints/mcp_ocr_v5 \
  --output vision/checkpoints/mcp_ocr_v6 \
  --epochs 12 --lr 0.0001 --device mps
```

--camera는 반복 가능하며 예전 단일 폴더 명령도 지원한다. --v6는 120+160 학습쌍과 정확한 v6 프리셋별20쌍/40테스트쌍을 요구한다. --prepare-only를 붙이면 검증과 병합만 수행한다. 이 경우에도 출력이 만들어지므로 다음 실행은 새 output 경로를 사용한다.

합성 train/val/test는 원래 split을 보존하고 카메라는 train에만 병합한다. 테스트 카메라는 병합하지 않는다.
10–15 epoch, 기본 LR 0.0001로 학습하며 kind별 metrics.json에 epoch별 검증 전체 문자열/자리 정확도·loss를 기록한다.
검증셋 전체 문자열 정확도로 best checkpoint를 선택한다. 현재 val은 기존 합성이므로 카메라 일반화를 보장하지 않는다.
--v6의 --real-test는 누수 사전 검증만 수행한다. 실제 테스트 평가를 학습 종료 시 자동 실행하지 않아 최종 비교용으로 남긴다.
training_manifest.json은 입력 경로·내용/라벨 fingerprint·split별 수·초기 checkpoint 경로·전처리 계약을 남긴다.
출력 폴더가 존재하거나 입력/초기 가중치와 포함 관계이면 실패한다. 원본 파일은 수정하지 않는다.

## 동일 카메라 테스트 비교

```sh
python vision/compare_camera_mcp.py \
  --test vision/data/camera_batches/v6_test_40 \
  --v5 vision/checkpoints/mcp_ocr_v5 \
  --v6 vision/checkpoints/mcp_ocr_v6 \
  --training-data vision/data/mcp_ocr_aligned \
  --training-data vision/data/camera_batches/sync_test_20261112_021206 \
  --training-data vision/data/camera_batches/v6_train_160 \
  --output vision/reports/v5_vs_v6_camera_01 --device mps
```

양 모델을 동일 test split으로 평가해 HDG/ALT 각각 문자열 완전 일치 비율, 표본 수, 차이(%p), checkpoint hash와 테스트 fingerprint를 comparison.json에 기록한다. 모델별 predictions.csv/errors.csv/summary.json도 생성한다. known merged_training_data와 학습 manifest까지 읽어 학습/테스트 중복을 재검사한다.
평가 중 테스트 데이터 변경은 실패한다. 출력 기존 폴더는 덮어쓰지 않는다.
결과를 보고 학습을 다시 조정했다면 이 테스트셋은 더 이상 미사용 테스트셋이 아니다. 최종 성능은 새로운 촬영 세션으로 평가한다.
테스트 조합은 2종뿐이므로 넓은 숫자/조건의 일반화 성능이나 실제 항공기 정확도로 표현하지 않는다.
모델 점수는 정확도가 아니다. 카메라 검출 실패까지 포함하는 E2E 정확도는 별도 실물 평가가 필요하다.

## 데이터·전처리 계약

- 컬럼/ASCII 숫자·길이·HDG 000–359/ALT 00000–99900, 빈 데이터·누락/깨진 이미지·중복 행/경로·경로 탈출/심볼릭 링크 탈출·동일 source의 중복 kind/미완성 쌍을 차단한다.
- 픽셀 hash로 카메라 내부 및 데이터셋 사이의 동일 이미지, 라벨 충돌과 split 누수를 차단한다. 합성 같은 split의 동일 픽셀/정답은 허용하지만 split/정답 충돌은 차단한다. 비슷하지만 다른 연속 프레임은 hash만으로 식별할 수 없으므로 별도 물리 세션이 필수다.
- 새 세션 ID의 교차 데이터셋 재사용을 차단한다. 과거 camera_0000 ID는 배치 내부 ID였으므로 배치별 namespace로 보존하고 픽셀 hash 누수 검사도 적용한다.
- 잘못 입력했지만 형식상 유효한 정답은 자동 검증할 수 없다. 촬영 당시 실제 숫자와 사람이 대조해야 한다. OCR 예측은 정답에 사용하지 않는다.
- 수집/live: camera ROI → camera_to_amber → align → 고정 RGB 이미지. 학습/eval은 이미 정렬된 이미지를 다시 align하지 않고 grayscale→bilinear 36n×48→float32/255를 적용한다.
- 공통 mcp_preprocessing.py와 픽셀/텐서 동등성 테스트로 일치를 확인한다. v6 checkpoint의 preprocessing 메타데이터를 읽어 명시적으로 v6를 불러온 웹 runtime도 같은 카메라 파이프라인을 쓴다. 기본 v3는 기존 amber 처리와 경로를 유지한다.
- CNN 테스트는 검출/전처리 성공 후 저장된 crop 조건의 정확도이다. 두 모델의 crop/정규화/테스트셋은 동일하다.

## 구현·검증·리뷰·인수인계

수정: collect_camera_mcp.py, finetune_camera_mcp.py, train_mcp_ocr_v2.py, evaluate_mcp_ocr.py, live_mcp_ocr.py, ocr_v3_runtime.py.
추가: mcp_camera_presets.py, mcp_preprocessing.py, mcp_dataset.py, compare_camera_mcp.py, test_v6_pipeline.py, 본 문서.
React 코드와 3D 디자인은 이번 요청에서 수정하지 않았다. 기존 ACK 연결을 그대로 사용한다.

검증 명령:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=vision:. python -m pytest \
  vision/tests vision/test_v6_pipeline.py vision/test_mcp_display_sync.py \
  -q -p no:cacheprovider --basetemp=/tmp/radar-v6-regression
```

자체 리뷰: 기존 v5/입력 덮어쓰기 차단, 사전 검증 후 출력 생성, 카메라 테스트 학습 유입 차단, 최적 epoch의 test 선택 방지, 해시/세션/잘못된 정답 검사, 기본 모델 변경 없음. 외부 리뷰는 미실행이며 PR/커밋은 생성하지 않은 현재 사용자 브랜치의 미커밋 변경이다. 새 실제 촬영과 MPS 공식 v6 학습, 태블릿/YOLO 실물 회귀 및 실사용 개선 확인은 남아 있다.

### 실제 실행 결과

- 기존 vision/tests와 신규 pipeline/sync 통합 실행: 67 passed. 이후 추가한 v6 CLI 테스트를 포함한 pipeline 9 passed (중복 제외 총68개 사례).
- v6 CLI 통합: 기존120+신규160 학습쌍/테스트40쌍 fixture 구성 검증, trainer와 합성 진단만 호출하며 카메라 test 미소비 확인.
- OpenCV/ACK 모의 수집: 테스트 40쌍, 두 프리셋 정답/20쌍 경계/N 전환/CSV test split, ACK false일 때 SPACE 저장0건 확인.
- 실제 v5 checkpoint 초기화 → 임시 작은 fixture에서 HDG/ALT 각각10 epoch → checkpoint/metrics/평가/모델 비교 보고서 생성 성공. 이는 구현 smoke이며 실제 카메라 정확도 개선 결과가 아니다. 출력은 임시 디렉터리이며 공식 mcp_ocr_v6 폴더를 생성하지 않았다.
- 기존120쌍 CSV240행과 v5 merged_training_data1244행 검증 통과. Python 구문, CLI help와 git diff --check 통과.
- 검증 중 기존 runtime 객체의 전처리 메타데이터 누락 호환성 실패3건을 발견하여 기존 amber fallback을 유지하도록 수정 후 전체 회귀 통과.
- 실물 신규 촬영, MPS 공식12 epoch 학습, 미사용 실제 카메라 v5/v6 비교와 기본 모델 전환은 미실행.

## 2026-11-12 실제 카메라 수집 재개 준비

새 `cnn_v6_workflow.py`는 diagnose / collect-train / collect-test / train / compare 단계를 제공한다. train --prepare-only는 별도 mcp_ocr_v6_preflight에 저장한다. 모든 단계는 --dry-run으로 원래 명령을 출력한다. 신규 수집은 blind_v2 YOLO와 confidence .5/3프레임을 사용하며 ACK, SPACE/N/Q, 기존 프리셋과 전처리를 보존한다. 학습은 기존120+신규160, v5 초기화,12 epoch, 독립 신규40 평가이며 기본 모델을 바꾸지 않는다.

기존 v6_train_160의 labels.csv는 실제 샘플 대신 헤더가 중복되어 있다. 이를 수정/삭제하지 않고 v6_train_160_02 / v6_test_40_02 및 session_02를 사용한다. 수집 창 시작과 0/160 상태, 태블릿 ACK를 확인했다. N 다음 터미널 Enter는 사용자 터미널이 필요하므로 에이전트 실행은 중단하고 동일 명령으로 재개한다.

```sh
python vision/cnn_v6_workflow.py collect-train
# 160쌍 완료 후 별도 물리 촬영 세션
python vision/cnn_v6_workflow.py collect-test
python vision/cnn_v6_workflow.py train --prepare-only
python vision/cnn_v6_workflow.py train
python vision/cnn_v6_workflow.py compare
```

validate_yolo_video.py에 --save-failure-frames N 추가: 안정 MCP이지만 readout 실패일 때만 원본과 panel/score/reason JSON을 최대 N개 저장한다. CNN 입력·게이트 기준은 변경하지 않는다. 진단은 `python vision/cnn_v6_workflow.py diagnose`이며 최초 실행 결과를 `vision/reports/cnn_v6_readout_diagnosis_01`에 보존했다. 300프레임 중 spatial299, temporal249, readout포함99; readout실패150 중30개 저장. 저장30개 모두 기존 panel 높이*.11보다 큰 숫자 크기의 밝은 component가 존재했다. 첫 실패 원본을 육안 확인했다. 이 관찰만으로 참 숫자 박스를 보장할 수 없으므로 휴리스틱/안전 임계값은 수정하지 않았다. 이 세션의 통과율은 정답 정확도가 아니다.

검증: 기존107 회귀 passed(4.41s), 실패 화면 저장 수량제한/JSON 사유/미통과 시 eligible0 검증 포함. git diff --check 통과. 실제 진단300프레임 실행 완료; 신규160/40 수집 완료·공식 v6학습·성능 비교는 아직 미실행. 변경 파일: cnn_v6_workflow.py, validate_yolo_video.py, test_yolo_blind_pipeline.py, 이 문서와 TODO. 사용자 미커밋 작업 보존.

### CSV 재개 오류 수정 및 실제160쌍 검증

사용자 실행 오류: 수집 중 샘플0개 상태로 종료했다가 재개하면 `if not existing` 조건이 헤더를 다시 썼다. collect_camera_mcp.py는 append 파일 위치가0인 경우에만 헤더를 쓰도록 수정했다. 실제 v6_train_160_02/labels.csv는 labels.csv.before-header-fix.bak로 원본 백업하고, 모든 필드가 헤더명과 정확히 같은 한 행만 제거했다. 이미지/정답320행은 보존했다. strict validator, v6 학습8조합별20쌍, 기존120쌍과 픽셀/세션 disjoint 검사 통과. v6_test_40_02/labels.csv는 아직 없다.

cnn_v6_workflow.py는 테스트셋 부재 또는 비교 시 v6 checkpoint 부재를 선행 검사하고, 하위 단계 실패 시 불필요한 wrapper traceback 없이 종료한다. 테스트셋 부재 안내 실제 확인; 준비/학습/비교는 미실행. 다음 행동은 collect-test로 별도 세션40쌍 수집 후 준비→학습→비교를 성공 시에만 순차 실행하는 것이다.

회귀: test_v6_pipeline.py/test_mcp_display_sync.py/vision/tests 68 passed(3.19s). 빈 배치 두 번 재개 후 헤더1개 유지 및 이후1쌍 저장/검증 사례 포함. git diff --check 통과. 미커밋, CNN/React와 안전 게이트 변경 없음.

### 합성 crop 좌표 컬럼 병합 오류 수정

실제 합성 CSV에는 필수6컬럼 외 crop_x1/y1/x2/y2가 있어 고정6컬럼 writer가 실패했다. finetune_camera_mcp.prepare는 필수컬럼+추가컬럼 합집합으로 저장하며 좌표값을 보존하고 카메라에 없는 값은 빈칸으로 기록한다. 원본 CSV/이미지는 수정하지 않는다. 실패한 preflight는 *_failed_20261112_114148로 보존한 뒤 원래 preflight 경로에 재준비 성공. 실제 신규 테스트40의 v6 조합/세션/중복 검증도 이번 준비에 포함됐다. merged 각kind train514/val134/test134; test134는 합성 테스트이며 독립 카메라40은 병합에서 제외된다.

회귀68 passed(2.72s), 합성 좌표보존/카메라 빈좌표 및 기존 split보존 시험 포함; diff --check PASS. 실제 --prepare-only 성공, 공식 학습/성능 비교 미실행. 다음 명령은 `python vision/cnn_v6_workflow.py train`이다. 준비 명령을 다시 실행하면 기존 출력 보호로 차단된다.
