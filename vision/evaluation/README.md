# 1주차 PoC 검증 기록

2026-10-10 · Python 3.12 / Pillow 12.3 / macOS Vision OCR. 정지 이미지 합성 fixture만 사용. 원본 실제 Cockpit 이미지·웹캠·서버 전송은 미검증.

- `vision/.venv/bin/python -m pytest vision/tests -q`: 13 passed. 숫자 형식·FL 변환·HDG 0/360·낮은 점수·blank·잘못된 크기·OCR 장애·시각 처리 확인.
- `vision/.venv/bin/python vision/evaluation/run.py --ocr-binary vision/.build/radar-ocr`: 아래 실제 OCR 결과. 5개 고정 기대 사례 통과, 1개 탐색 사례. 학습/튜닝과 분리된 평가 세트가 아니며 정확도로 일반화하지 않는다.

| 합성 입력 | ALT 결과 | HDG 결과 | 관찰 |
| --- | --- | --- | --- |
| 정상 | 3000 | 270 | 정답 일치 |
| 설정 변경 | 3500 | 290 | 정답 일치 |
| 북쪽 | 16000 | 0 | 0을 누락으로 취급하지 않음 |
| 고도 영역 전체 가림 | null | 270 | blank_roi |
| 방위 360 | 3000 | null | out_of_range |
| 흐림 (탐색) | null | 270 | ALT invalid_format; 흐림 일반 감지 완료 아님 |

출력 JSON·ROI·프레임은 ignored `vision/output/evaluation/`에 있다. 합성 이미지와 정답은 `fixtures/`, `labels.json`에 분리했다. 생성 명령은 `vision/.venv/bin/python vision/evaluation/generate_samples.py`이며 Pillow 기본 폰트와 명시적인 값으로 자체 생성한다. OCR 코드에는 labels 입력이 없다.

미실행: 반사·부분 가림·실제 폰트/7세그먼트·해상도/각도 변화·영상 지연·카메라 끊김. 다음은 실제 화면과 카메라 확보, ROI/단위 확인, 작은 정답 세트로 검증이다.

## 사용자 제공 Cockpit 참고 사진

사용자가 이런 패널을 촬영한다고 가정하도록 제공한 참고 사진(1448×1086)에서 중앙 위 HEADING·ALTITUDE 숫자 창을 지정했다. 설정은 `vision/configs/cockpit-reference.json`이다. 이 사진에 고정된 픽셀 ROI이며 실제 카메라 위치/해상도/촬영 조건 확정은 아니다.

- ALTITUDE ROI `[749, 272, 818, 291]` → OCR `10000`, feet.
- HEADING ROI `[678, 272, 720, 291]` → OCR `272`, degrees.
- 원문 숫자와 ROI 이미지를 직접 대조하여 두 값이 일치함을 확인.
- 출력은 로컬 ignored `vision/output/reference/`에 보관. 원본 사진은 Git 추적 fixture로 복사하지 않음.
- 촬영 시각 미상, 정지 이미지 1개 확인이며 웹캠/여러 각도/연속 변경 성능을 입증하지 않는다. 다른 사진에는 ROI를 다시 지정해야 한다.

아래 큰 비행 화면이나 별도 원형 계기의 현재 상태와, 위 숫자 창의 설정값을 혼동하지 않는다. 숫자 창이 있는 이 참고 화면에는 기존 OCR을 적용할 수 있다. 바늘/눈금만 있는 대상의 인식은 여전히 미구현이다.

## 고정 지지대 MCP 구도 추가 검증

사용자 두 번째 사진의 3개 창 및 설치 계획은 [촬영 기준](../docs/camera-setup.md)에 기록했다. 추가 후 테스트 20 passed. speed 250/altitude 10000 인식, heading은 OL2/invalid_format으로 null. Mach 소수는 파서 테스트만 했으며 실제 Mach 사진/모드 변경은 미검증.

## HEADING 오류 수정 검증

- 원본 ROI OCR: OL2. grayscale + 4배 Lanczos 확대: 270. invert/threshold는 채택하지 않음.
- 최종 설정은 heading에만 전처리 적용. 같은 두 번째 사진에서 altitude=10000, heading=270, speed=250, 모든 reason=null 확인.
- `vision/.venv/bin/python -m pytest vision/tests -q`: **29 passed**. 전처리 옵션 유효성·필드별 적용·원본과 OCR 입력 근거 분리·기존 실패 처리 회귀 포함.
- `vision/.venv/bin/python vision/evaluation/run.py --ocr-binary vision/.build/radar-ocr --output-dir vision/output/regression-heading-fix`: 기존 고정 기대 사례 5개 통과, 흐림 1개 탐색 결과 유지.
- actual 결과는 ignored `vision/output/mcp-heading-fixed/`. 새 예제는 `contracts/examples/mcp-observation.json`.
- 여러 창에 공통 전처리를 적용한 중간 실험은 speed 052 오인식으로 거부했다. 최종 사진은 tuning에 사용한 샘플이며 독립 평가 데이터/실장비 성공률이 아니다.

## output 정리 이후 확인 위치

2026-10-10 문서 보관 요청으로 중복 실행 output을 삭제했다. 위의 output 경로는 당시 실행 기록이며 현재 보관 위치가 아니다. 최신 사진·최종 JSON·ROI와 전처리 근거는 [팀 공유 문서](../../docs/vision/README.md)에 보존했다. 첫 번째 참고 사진과 중간 실험 원본은 포함하지 않고 최종 MCP 사진 1개만 공유한다.
