# 실제40장 YOLO 게이트·IoU 진단

2026-11-12 사용자 요청. 기존 보고서 yolo_real_compare_01과 실제 가중치/검토 이력/원본 사진을 분석하고 같은40장으로 MPS 재평가했다. 실제 파일을 확인한 수치이며 CNN/React/원본 라벨/모델/임계값은 변경하지 않았다.

## 결론

IoU의 정상 박스 교집합/합집합 공식은 맞았다. 기존 mean_top1_iou는 원래도 미검출을0으로 포함했다. 이번에는 두 모델 모두 score≥.1에서40/40장에 박스가 있어 전체 평균과 탐지된 이미지 평균이 같다. '박스가 존재함', 'IoU≥.5', 'AP recall', '게이트 통과'는 서로 다른 통계다.
기존 IoU .9998은 독립 수동 정답에 대한 거의 완벽한 위치 정확도로 해석할 수 없다. 테스트40장의 review_audit는 전부 HUMAN_ACCEPT이며, 정답이 기존 baseline_v7가 제안한 좌표와 모두 IoU≥.999로 일치했다. 이미지의 학습/테스트 session/hash 분리는 통과했지만 라벨에는 proposing-model anchoring이 있다. 사람이 실제로 검토하지 않았다고 단정하지는 않는다. 다만 모델 제안을 숨긴 독립 라벨이 아니므로 기존 모델에 유리한 평가 기준이 될 수 있다.
샘플00000/00001/00015 오버레이를 검토했으며 일부 정답 박스는 MCP 외에 윈드실드 하단/EFIS 또는 아래 주 계기 영역까지 포함하는 등 외곽 기준을 재확인할 필요가 있다. 예측과 기존 제안 라벨이 일치했다는 사실만으로 MCP 전체 영역이 정확하다고 판단하지 않는다.

## 같은 테스트 재평가

| 지표 | 기존 baseline_v7 | 신규 mcp_yolo_real_v1 |
| --- | ---: | ---: |
| Precision | .413968 | .660064 |
| Recall | .750000 | .750000 |
| mAP50 | .446097 | .725584 |
| mAP50-95 | .178109 | .227527 |
| 예측 박스 존재 / 전체 (score≥.1) |40/40|40/40|
| 미검출 이미지 |0|0|
| top-1 IoU 전체 평균 (미검출=0) |.999836|.624171|
| top-1 IoU 탐지 이미지 평균 |.999836|.624171|
| IoU≥.5 이미지 |40/40|30/40|
| IoU≥.5 이미지의 평균 |.999836|.685732|
| spatial gate 통과 |1/40 (2.5%)|0/40|
| spatial 통과 이미지의 평균 IoU |1.000000|해당 없음|
| validator 출력 top-1 IoU 전체 평균 |.599630|.626197|

IoU는 원본1920×1080 이미지의 continuous xyxy 픽셀 좌표로 계산하며 정규화된 YOLO xywh를 loader에서 복원한다. GT와 prediction을 바꾸거나 GT에 가장 가까운 후보를 골라 평균내지 않는다. 동일/부분 겹침/포함/분리/퇴화/NaN에 대한 정답 테스트를 추가했다. invalid/missing IoU는0이다. detected 평균의 분모가0이면 null이다.

## 게이트 탈락 원인

- 기존: AMBIGUOUS_PANELS 37장, LOW_OR_MISSING_PANEL_SCORE 2장, 통과1장(00026.png, score .537217). 기존 top-score 범위 .390075–.986926. 높은 top IoU라도 다른 위치에 높은 후보가 있으면 보류하는 것이 현재 정책이다.
- 신규:40장 모두 confidence<.5, 범위 .249512–.396180, 평균 .307668. 즉 위치/면적·시간 안정성 때문에0%가 된 것이 아니라 실제 첫 차단 조건인 confidence 미달이다. 모든 조건을 독립적으로 검사해 보니 이 테스트의 신규 박스에는 추가 공간 조건 탈락이 없었다.
- 공간 gate는 정지 이미지 진단을 위해 stable_frames=1로 평가한다. 기존 비교도 동일했다. 실제 운용의 기본3프레임/IoU .8은 유지했고, 정지 이미지를 연속 영상인 것처럼 취급하지 않는다.
- 통과1장은 CNN 전달 승인으로 표현하지 않는다. 실시간 경로의 시간 안정성, MCP 안쪽 HDG/ALT 두 readout 검출·범위 검증이 추가로 필요하다. GT는 평가에만 쓰며 runtime 입력/선택에 넣지 않는다.

### 유지한 정책

candidate score floor .1, top confidence .5, 별도 후보 score≥.3 및 top과 IoU<.5이면 모호성 차단, 이미지 외곽≤1px 차단, 각 변12px 미만 차단, 면적비 .003–.9, 최근3프레임 IoU≥.8. 종횡비는 진단값으로 기록하지만 기존 gate에는 별도의 aspect ratio 구간이나 화면 중앙 위치 prior가 없다. 테스트를 보고 새 비율 기준을 임의로 넣지 않았다.

## AP와 단일 이미지 IoU의 추가 차이

설치된 Ultralytics8.4.209의 실제 callback/pre_transform에서 확인했다.

| 경로 | 실제 입력 H×W | 패딩 | NMS IoU | score floor |
| --- | --- | --- | --- | --- |
| validator (.val, AP) |576×992|rect batch pad .5|.7|.001|
| 단일 .predict (운용형 진단) |544×960|최소 rect letterbox|.5|.1|

둘 다 imgsz=960이지만 실제 tensor 크기/패딩과 NMS 설정이 다르다. 따라서 AP와 기존 top-1 IoU를 동일 예측 결과의 통계로 직접 해석하면 안 된다. validator의 실제 예측 .txt도 저장해 원본 픽셀 좌표로 복원한 별도 IoU를 보고한다. .txt 좌표의 출력 정밀도에 따른 작은 반올림 오차가 있을 수 있다.
해상도/패딩의 차이가 단일 원인이라고 인과를 단정하지 않으며 실제 출력 차이와 설정 차이를 함께 기록한다. 설정을 바꿔 유리한 결과를 골라내지 않고 기존 경로의 수치를 그대로 재현했다. 두 모델은 각 경로에서 동일 설정으로 평가했다.

## 산출물

최종 폴더 `vision/reports/yolo_real_compare_03_diagnostics/`:

- index.html: old/new 및 primary reason 필터,40장×2모델 오버레이 링크.
- per_image.csv:80행, score/IoU/탐지 여부/전체 탈락 사유/후보 수/박스 크기/면적비/종횡비/라벨 방식/validator IoU.
- boxes.json: 전체 후보 좌표·점수·GT IoU, 경쟁 후보의 top IoU/모호성 판정, 조건별 원인, actual preprocess 설정.
- comparison.json: 전체/탐지/IoU≥.5/게이트 기준 분모·통계, 원본과 가중치 SHA256, test fingerprint, 라벨 출처/teacher 일치율.
- old/overlays, new/overlays:80장. 녹색GT, 빨간 top 예측, 주황 경쟁 후보. 사유/score/IoU를 사진에 기록했다.
- old/labels, new/labels: 실제 AP validator 예측. 원본 정답 label과 별도 output이다.
- diagnosis.md: 자동 생성 영문 요약/기준/권고.

원래 보고서01, 중간 진단02, 원본 데이터와 가중치는 덮어쓰지 않았다. 보고서01과03의 test fingerprint 및 양쪽 모델 hash 일치를 확인했다.

## 다음 라벨·학습 개선

1. 모델 박스를 숨기고 새 촬영 세션에서 독립 수동 라벨링한다. MCP 숫자 창/선택 노브/조작부 전체를 일관되게 포함하고 EFIS, 윈드실드, 아래 flight displays는 제외한다. 이미 공개된 이번40장을 다시 '미사용 최종 테스트'라고 부르지 않는다.
2. train/val도 기준을 점검한다. 현재 감사 기록: train_near 39 ACCEPT/1 DRAG, train_far35/5, train_angle30/10, val28/2, test40/0. 서로 다른 외곽 기준을 섞으면 위치/점수 학습이 불안정할 수 있다. 이는 가설이며 라벨을 임의 수정하거나 이번 실행에서 재학습하지 않았다.
3. 흐린 사진은 초점/노출을 고정하고 선명한 MCP 외곽을 확보한 뒤 거리·기울기·빛/반사·화면 배율을 다양한 별도 세션에서 수집한다. 누락·잘림은 명시적으로 검토한다.
4. 라벨 기준을 먼저 통일한 다음 validation에서만 augmentation/학습률/학습 길이·점수 보정을 검토한다. test를 보고 confidence .5를 내리거나 모호성 검사를 끄지 않는다. 현재 신규 모델은 운용 gate를 통과하지 못하므로 mAP 개선만으로 자동 채택하지 않는다.

## 구현·검증·리뷰·인수인계

변경: compare_yolo_camera.py와 mcp_yolo_gate.py. 추가: yolo_gate_diagnostics.py, test_yolo_gate_diagnostics.py, 본 문서/최종 보고서. CNN 모델과 React Cockpit 코드는 수정하지 않았다.
수식의 정상 박스 동작과 게이트 숫자는 그대로이며 policy()로 기존 수치를 공개했다. malformed/missing IoU0 처리와 파일명 충돌 없는 validator 예측 연결을 보완했다.
검증: 기존 vision/CNN/ACK/YOLO/자동수집 포함 회귀를 실행한다. 실제 MPS에서 동일40장 양 모델 .val/.predict 재평가와80장 오버레이 생성, 전체 원본 hash 불변을 확인했다. 정지 영상 평가이며 live camera/실시간3프레임 게이트 E2E는 미실행이다.
자체 리뷰에서 GT를 후보 선택에 사용하지 않는 것, 미검출 분모0 및 detected 평균null, threshold·시간 게이트 유지, annotation teacher bias와 전처리 차이, 출력 폴더/원본 보존을 확인했다. 외부 리뷰/커밋/PR은 미실행이다. TODO 상태는 verifying이며 독립 정답 라벨 검증과 최종 실물 채택 인수는 남아 있다.

재실행은 이미 존재하지 않는 새 output을 사용한다.

```sh
python vision/compare_yolo_camera.py \
  --test vision/data/yolo_camera_confirmed/test \
  --old ../Boeing_RADAR/runs/detect/vision/checkpoints/mcp_yolo/baseline_v7/weights/best.pt \
  --new vision/checkpoints/mcp_yolo_real_v1/fit/weights/best.pt \
  --seen vision/data/mcp_blender_v7 \
  --seen vision/data/yolo_camera_confirmed/train_near \
  --seen vision/data/yolo_camera_confirmed/train_far \
  --seen vision/data/yolo_camera_confirmed/train_angle \
  --seen vision/data/yolo_camera_confirmed/val \
  --output vision/reports/yolo_real_compare_04_diagnostics --imgsz 960 --device mps
```

### Precision의 confidence 지점과 검증 결과

설치된 Ultralytics utils/metrics.py의 ap_per_class는 평균 F1 곡선의 최대 지점에서 Precision/Recall을 취한다. 따라서 신규 Precision .660은 confidence .5에서66%가 통과한다는 뜻이 아니다. 이번 고정 .5 gate에서 신규 top score가 모두 .3962 이하이므로0/40과 모순되지 않는다.
최종 회귀: **96 passed**, skip 없음. 기존 CNN/ACK/YOLO/자동수집89사례에 새 진단7사례를 더했다. 마지막 파일명 연결 테스트에서 정규화 좌표 복원의 float 반올림을 assertAlmostEqual로 검사했다. 실제 MPS 동일40장 재평가에서 원래 Precision/Recall/mAP 수치와 top IoU/게이트 통과율을 그대로 재현했고 모델 hash 및 test fingerprint가 원래 보고서와 같았다. git diff --check와 시각화 샘플 확인도 완료했다.
