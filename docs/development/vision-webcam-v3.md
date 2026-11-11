# Boeing 737 조종석 + 웹캠 OCR v3 실행 기록

2026-11-11 사용자 요청. 브랜치 `feat/vision-ai`, 선행 커밋 `e637a03`.
원격 fetch 후 HEAD와 origin/feat/vision-ai 일치 확인. 기존 Blender/train_digits 변경과 untracked GLB/reports를 보존했다. 신규 변경은 미커밋이며 기존 WI 전체의 실장비 인수를 완료 처리하지 않는다.

## 실행

Node는 프로젝트 기준 22.20+ 또는 24.12+를 사용한다. 이 Mac에서는 설치된 `nvm use 24.18.0`을 사용한다. Python은 기존 torch/OpenCV/FastAPI/uvicorn/Pillow/numpy가 설치된 가상환경을 활성화한다. backend 추가 의존성은 `backend/requirements.txt`를 따른다.

```sh
# 저장소 루트, 가상환경 활성화 후
cd frontend
npm install
cd ..
sh scripts/run-cockpit-vision.sh
```

동일 포트의 서버가 이미 켜져 있으면 중복 실행하지 않는다. 스크립트는 시작 전 포트·모델·Vite 존재를 확인하고, 종료 시 자신이 시작한 서버만 중단한다. `RADAR_PYTHON`으로 다른 Python 실행파일의 절대 경로를 지정할 수 있다.

- 조종석/OCR: http://127.0.0.1:5173/cockpit
- 기존 사진 MCP: http://127.0.0.1:5173/
- 기존 운영: http://127.0.0.1:5173/operations
- 기존 backend: http://127.0.0.1:8000/docs
- OCR 추론 서버: http://127.0.0.1:8765/docs, `/health`

개별 실행은 backend에서 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, 저장소 루트에서 `python -m uvicorn vision.ocr_web:app --host 127.0.0.1 --port 8765`, frontend에서 `npm run dev -- --host 127.0.0.1`이다.

## 화면 사용

`/cockpit`의 3D는 기존 다른 로컬 worktree의 Three.js Cockpit3D.jsx/cockpit3d.css를 복사해 사용하며 원본 worktree는 변경하지 않았다. `frontend/public/models/cockpit.glb`를 읽는다. 전체/조종석/MCP 정면 시점, 숫자 직접 입력과 노브 수동 조작을 유지한다. 사진 MCP·운영·조종사 경로는 유지했다.

웹캠 시작 → 브라우저 카메라 권한 허용. 전체 프레임에서 주황색 숫자 묶음을 찾아 5자리 ALT와 같은 줄 왼쪽의 가장 가까운 3자리 HDG를 자동으로 선택하고 연속 추론한다. 수동 영역 선택은 없다. 두 창을 동시에 찾지 못하거나 후보가 여러 개면 값·안정화 이력을 비우고 탐색을 계속한다. 지원 대상은 HDG가 ALT 왼쪽에 있는 현재 MCP 배치이며 범용 계기판 탐지기가 아니다. Mac 내장 카메라로 같은 Mac 화면을 직접 찍을 수는 없으므로 태블릿/외부 화면을 향하거나 외장 카메라를 사용한다.

카메라를 열 수 없으면 macOS 시스템 설정 → 개인정보 보호 및 보안 → 카메라에서 브라우저 또는 Python/실행 앱 권한을 확인한다. 실제 프레임은 저장하지 않고 선택 ROI만 루프백 추론 서버로 전송한다.

별도 OpenCV 창:

```sh
python -m vision.live_mcp_ocr --source 0 --checkpoints vision/checkpoints/mcp_ocr_v3 --stable-frames 3
```

H: HDG ROI, A: ALT ROI, Enter/Space 확정, C 취소, R 초기화, Q 종료. 브라우저와 OpenCV가 동시에 같은 카메라를 점유하면 한쪽을 중단한다. CPU가 기본이며 MPS 장치의 일부 pooling 호환성은 별도 검증 대상이다.

## 입력 → 처리 → 출력과 안전 경계

브라우저 getUserMedia → 전체 프레임 JPEG(최대 1280×960) → Vite `/ocr-api/infer-frame` proxy → 주황색 숫자 창 자동 탐지 → 독립 FastAPI `vision.ocr_web` → 기존 `preprocess_mcp_ocr.align` 주황색 추출/기울기 보정 → 별도 HDG 3자리·ALT 5자리 CNN → 값/미보정 모델 점수/실패 사유/서버 수신 UTC. 모델은 지정된 v3 파일만 로드하고 재학습하지 않는다.

HDG는 000–359만 허용하고 000을 결측으로 처리하지 않는다. 판독 불가는 null이다. 연속 3회 같은 값만 STABLE, 그 외 CHECK이며 이는 운항 안전 판정이 아니다. 초기화/ROI 변경/중지/카메라 종료/통신 실패/동결/1.5초 넘는 응답 공백 시 값과 안정화 이력을 비운다. 동시에 여러 추론 요청을 보내지 않는다. UTC는 카메라 센서 시각이 아니라 서버 수신/처리 시각이다.

OCR 값은 조종석 수동 선택값과 분리돼 있고 자동 변경이나 기존 운항/관제 비교 API 전송은 하지 않는다. 실제 조종석 정확도·반사·부분 가림·강한 원근·동결된 드라이버 입력은 별도 검증이 필요하다. STABLE이 반복 오인식을 배제하지 않는다.

## 검증

- frontend production 빌드 성공. 초기 전체 번들 크기 경고는 남는다.
- 기존 frontend 포함 56개 테스트 통과: 연속 동일값·0도·누락·변경·시간 공백 회귀 포함.
- `python -m pytest vision/tests/test_ocr_v3_web.py -q`: 3개 통과. blank→null, 999→거부, 000→유지, 잘못된 이미지422, 필드별 독립결과/UTC 확인. private 모델이 없는 환경에서도 실행되는 단위 테스트.
- 실제 서버 health/docs 및 frontend HTTP200 확인.
- Chrome Metal에서 GLB ready, MCP HDG270/ALT03000 시각 확인. 합성 카메라(Blender fixture)를 브라우저 ROI로 드래그하고 실제 v3 API에서 HDG052/ALT34600 및 STABLE 확인. 점수0.968/0.929는 정확도 보장이 아니다. 중지·재시작·통신 차단 시 값/STABLE 초기화, 기존 `/` MCP 경로 확인, 브라우저 JS 예외0건.
- 실제 OpenCV AVFoundation: 카메라0 open/read 성공, 1920x1080. 일반 Chrome 창의 실제 getUserMedia도 1280x720 readyState4 확인. 헤드리스 Chrome의 native 카메라는 NotSupportedError였으므로 실제 카메라 검증은 일반 창에서 수행했다. 실제 계기판을 카메라에 비춘 정확도와 반사/가림 조건은 미검증.
- 학습 데이터와 체크포인트 총 3,683개 파일의 작업 전후 SHA256이 모두 동일함을 확인했다. 1,004장 데이터의 삭제·변경과 재학습은 하지 않는다.

자체 리뷰: OCR 실패를 숫자 불일치로 분류하지 않음, 과거 STABLE의 현재 표시 제거, 수동 조작과 OCR 분리, API/model score를 운항 정확도로 표시하지 않음. 외부/사람 코드 리뷰·PR 제출은 수행하지 않았다.

## 이번 요청의 변경 파일

- frontend: `package.json`, `package-lock.json`, `vite.config.js`, `README.md`, `src/main.jsx`
- 조종석·웹캠 UI: `src/Cockpit3D.jsx`, `src/cockpit3d.css`, `src/CockpitVision.jsx`, `src/WebcamOCR.jsx`, `src/cockpit-vision.css`, `src/ocr-stability.js`
- frontend 검증: `tests/ocr-stability.test.js`, `tests/cockpit-vision.smoke.mjs`
- Vision: `vision/ocr_v3_runtime.py`, `vision/ocr_web.py`, `vision/live_mcp_ocr.py`, `vision/tests/test_ocr_v3_web.py`
- 실행·기록: `scripts/run-cockpit-vision.sh`, `docs/development/vision-webcam-v3.md`, `docs/spec/todo.md`

기존 `vision/blender_render_mcp.py`, `vision/train_digits.py`, `frontend/public/models/`, `vision/reports/`의 로컬 변경은 이 요청의 신규 구현과 구분하며 보존했다.

브라우저 회귀 재현: 세 서버 실행 후 frontend에서 `node tests/cockpit-vision.smoke.mjs`. 기존 `vision/data/mcp_blender_digits_fixed/ocr_manifest.csv`와 그 PNG, 지정된 v3 모델을 사용하는 로컬 fixture 통합 테스트다. Chrome 경로는 `RADAR_CHROME_PATH`로 지정 가능하며 Mac Metal 경로를 사용한다. fake 카메라 스트림을 쓰므로 실제 촬영 정확도 검증으로 계산하지 않는다.


## 2026-11-11 자동 숫자 창 탐지 후속

- 요청: 웹캠 시작만으로 계기판 위치 탐지부터 연속 OCR까지 동작. `vision/auto_windows.py`는 amber mask의 여러 크기 연결 성분과 세로 투영을 사용해 3/5자리 묶음을 찾는다. 5자리 ALT와 정렬된 가장 가까운 왼쪽 3자리만 HDG 후보로 삼아 IAS를 피하고, 후보 쌍이 정확히 하나일 때만 반환한다. 영상 속 숫자를 먼저 읽거나 관제/수동 설정값을 탐지에 사용하지 않는다. 고정 픽셀 ROI·학습 라벨 입력은 없다.
- `vision/ocr_web.py`의 `/infer-frame`은 크기를 제한한 전체 영상을 받고 매번 탐지한 ROI를 기존 v3 모델로 읽는다. 위치 없음/다중 후보는 두 필드 null과 사유로 반환한다. 기존 `/infer` crop API는 유지한다. 프레임·학습 데이터·체크포인트를 저장하거나 재학습하지 않는다.
- `frontend/src/WebcamOCR.jsx`에서 수동 드래그 UI를 제거하고 전체 프레임 단일 요청 루프·탐지 사각형 표시로 교체했다. 위치 상실·큰 위치 변경·1.5초 공백·통신 장애·중지 때 이전 값과 안정화 이력을 비운다. 감지된 위치를 계속 고정하지 않고 매 프레임 다시 찾는다.
- 검증: `vision/tests/test_auto_windows.py` 및 `test_ocr_v3_web.py` 6 passed. 이동·IAS 배제·빈 영상·ALT 없음·다중 후보·000 유지·정상 후 탐지 실패 시 null·잘못된 프레임422를 확인했다. frontend `npm test` 56 passed. 브라우저 smoke에서 ROI 드래그 없이 웹캠 시작만으로 실제 v3 모델 HDG052/ALT34600 및 STABLE, 중지/재시작/연결실패 초기화, 기존 MCP 경로, JS 예외0건을 확인했다. 입력은 Blender 합성 영상이며 실제 웹캠 정확도 검증이 아니다.
- 자체 리뷰: 위치 불확실 시 이전 값 재사용 없음, 000과 누락 구분, 자동 Cockpit 제어/서버 관제 전송 없음. 탐지는 주황색·자리수·현재 MCP 상대 배치에 의존하는 실험 규칙이다. 백색 숫자, 가림/반사, 매우 작은 글자, 강한 원근, 주황색 배경 및 비슷한 무늬에서 누락·오탐 가능성이 남는다. 반복 동일값이 정답을 보장하지 않는다. 실제 촬영 인수와 외부 리뷰는 미실행이며 변경은 `feat/vision-ai`의 미커밋 상태다.


## 실제 촬영 탐색 실패 후속

실제 웹캠 프레임을 임시 경로에서 검사했다. 초기 프레임에는 강한 조명 반사·흐림이 있었고, 초점 대기 후 프레임에는 육안으로 숫자가 보이지만 기존 amber 임계값/열 투영이 획을 분리하여 탐지에서 제외했다. `auto_windows.py`에 촬영 색상용 보조 마스크와 여러 열 점유 조건을 추가하고 조건별 ROI가 IoU .65 이상으로 일치할 때만 채택한다. 후보가 다른 위치를 가리키면 보류한다. 실제 JPEG 압축도 통과시켜 확인했다.

실행 중인 Vite 프록시의 `/ocr-api/infer-frame`에 같은 실제 촬영 프레임을 보내 HTTP200, HDG/ALT 자동 ROI 반환을 확인했다. 그러나 v3 모델은 이 프레임을 낮은 점수로 잘못 판독했다. .75 미만 모델 점수는 실험적 보류 문턱으로 null/LOW_MODEL_SCORE를 반환하도록 변경했고, UI는 위치 탐색 실패와 위치 탐지 후 판독 보류를 구분한다. .75는 검증된 확률/정확도 문턱이 아니다. 실제 프레임 최종 점수는 HDG 약 .427, ALT 약 .391이며 두 값 모두 null이다. 실제 숫자 인식 성공으로 계산하지 않는다.

추가 회귀: 옅은 주황색 탐지와 낮은 점수 null 처리 포함 단위8개, 기존 합성 카메라 브라우저 회귀(HDG052/ALT34600 자동 탐지·STABLE·오류 초기화), frontend 빌드 통과. 라이브 장시간 정확도·이동/반사 일반화·체크포인트 개선은 미검증/미수행이다. 학습 데이터/체크포인트를 수정하거나 실제 카메라 이미지를 저장소에 추가하지 않았다.


## 웹캠 학습용 캡처와 사람 확인 정답 수집

사용자 요청으로 `/cockpit` 웹캠 패널 아래에 수집 기능을 추가했다. 웹캠 시작 → **학습용 장면 캡처** → 고정된 전체 영상과 HDG·ALT crop 확인 → HDG 3자리(000–359), ALT 5자리 정답 직접 입력 → 두 창과 정답 확인 체크 → **정답 확인 후 저장** 순서다. 숫자가 안 보이거나 자동 crop이 다른 항목이면 취소한다. OCR 결과나 모의 계기판 설정값으로 정답을 자동 채우지 않는다. 실시간 영상이 바뀌어도 고정된 캡처를 저장한다. 같은 장면을 반복하기보다 표시값·거리·각도·밝기를 바꾸며 수집한다.

- `vision/webcam_collection.py`: `/dataset/preview`가 전체 영상을 받아 현재 자동 ROI를 찾고 고정 crop을 반환한다. 이때 디스크에는 쓰지 않는다. draft는 메모리에 최대32개·10분간 유지한다. `/dataset/save`는 명시적 확인과 정답 형식을 검증한 뒤 원본 전체 프레임·두 crop·label.json을 같은 sample 폴더에 임시 생성 후 원자적 rename으로 확정한다. 동일 token/정답 재시도는 같은 receipt를 반환하며 다른 정답의 재저장은409다. 실패 시503으로 알리고 같은 캡처 재시도를 허용한다. 취소/만료 draft는 저장할 수 없다.
- 저장 위치: ignored `vision/data/webcam_labeled/<session_id>/<sample_id>/`의 `frame.jpg`, `hdg.jpg`, `alt.jpg`, `label.json`. metadata에는 사람 확인 정답 문자열, ROI, 서버 수신/라벨 시각, 실제 저장 프레임 및 입력 프레임 SHA256을 구분한다. crop은 저장 전 미리보기와 같은 바이트다. 새 촬영 세션 버튼은 다른 촬영 조건 묶음을 시작한다. split은 `unassigned`이며 데이터 준비 단계에서 촬영 세션 전체를 train/val/test 중 하나에 배정해야 한다. 연속 프레임을 무작위로 학습/평가에 나누지 않는다.
- `frontend/src/TrainingCapture.jsx`: 정답 공란 시작·확인 체크·형식 검사, 고정 장면/crop 표시, 실패 메시지, 저장 수와 세션 변경, 취소를 제공한다. 요청 시간 초과는 같은 token 재시도 대상으로 남기고 성공이 확인된 draft는 폐기한다. 기존 `WebcamOCR.jsx`의 자동 추론과 별도로 동작한다.
- 검증: `test_webcam_collection.py` 포함 Vision 관련12개 통과. 확인 전 미저장, 000/03000 유지, 잘못된 형식/360/확인false 거부, 고정 프레임·crop 크기, 취소/만료/위치 없음, 중복 요청과 다른 정답 충돌, 디스크 오류 후 재시도, 세션별 분리를 확인했다. frontend56개와 빌드 통과(기존 번들 경고 유지). 브라우저에서는 실제 preview API에 합성 카메라 프레임을 보내 미리보기와 공란 정답·확인 전 저장 비활성·직접 입력값 전송·저장 메시지를 확인했다. browser save만 mock하여 합성 샘플을 실제 학습 폴더에 섞지 않았고, 실제 파일 저장은 별도 임시 디렉터리 API 테스트로 검증했다. Git ignore 확인 통과.
- 자체 검토: 값의 자동 정답화 없음, 저장이 확인되기 전 성공 표시 없음, 미확인 프레임 자동 수집 없음, 기존 데이터/체크포인트/학습 코드 변경 없음. 실제 사용자의 정답 확인 캡처 저장 및 새 데이터 학습·평가는 아직 수행하지 않았다. 수집 JSON은 향후 학습 CSV 변환과 촬영 세션 단위 분리가 필요하며 이 변경은 학습 실행/모델 교체 기능을 포함하지 않는다. 외부 리뷰/PR·커밋은 미실행이며 `feat/vision-ai`의 기존 작업을 보존한 미커밋 변경이다.
