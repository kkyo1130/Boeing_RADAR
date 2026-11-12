# ZIP Whisper·BERT·OCR 연결

원본: RADAR-Mac-740df89, source commit `740df89abc1eccd152c7a180a82ca8618230d33f`.

```sh
bash scripts/run-zip-ai.sh "$HOME/Downloads/RADAR-Mac-740df89"
```

운영 화면은 http://127.0.0.1:5179/operations, API는 8019이다. 기존 ZIP의 5178/8018 서버와 비행은 유지한다. 새 프로젝트 서버의 DB는 `.demo/zip-ai.db`이며 새 비행을 시작한다. ZIP 폴더의 assets와 .venv를 계속 사용하므로 해당 폴더를 이동/삭제하면 실행할 수 없다. 기본 Python은 ZIP의 Python 3.11 가상환경이며 `RADAR_AI_PYTHON`으로 변경할 수 있다. `backend/requirements-zip-ai.txt`는 별도 환경 준비용이다. ZIP 환경에는 현재 리포트 코드가 요구하는 reportlab/pypdf도 필요하다.

Whisper는 ZIP의 `assets/model`, BERT는 `assets/bert-hybrid-model`을 참조한다. 모델 다운로드/학습은 실행하지 않는다. BERT 소스와 필요한 숫자 문법은 `speech/zip_ai`에 원본 그대로 가져왔으며 내부 import만 조정했다. 기존 서버 문법을 덮어쓰지 않는다. BERT 후보 불일치·모델 장애는 판단 보류로 전달한다. 점수는 보정된 정확도가 아니다.

OCR의 Swift 및 Python 인식 코드는 ZIP과 기존 프로젝트가 동일하다. 기존 코드를 사용해 `.demo/bin/zip-radar-ocr`를 빌드한다. ALT·HDG 영역은 수동 지정하며 자동 영역 탐지는 포함하지 않는다. 인식 결과는 기존 안정화·근거·서버 판정 경로를 사용한다.

검증 기록: [WI-07](../spec/009-evaluation-demo/workitem/wi-07.md).

## 음성·운영·Vision·리포트 통합 후속

ZIP의 정식 `app.services.speech` 모듈을 사용한다. 초기 임시 `speech/zip_ai` 중복 모듈은 제거했다. ZIP의 마이크/파일 ATC, 복창 문형·호출부호 접미형, 파일럿 화면을 함께 반영했다. 기존 상세 리포트/PDF/접근 권한과 모의 MCP 화면은 보존했다.

- `/operations`: 운영 화면. 파일럿 화면과 Vision AI 화면 링크.
- `/pilot?flight=<새 비행 ID>`: ZIP 파일럿 화면.
- `/report?flight=<비행 ID>`: 기존 상세 리포트/PDF.
- `/cockpit`: 보존한 Vision LAB의 자동 창 탐지·CNN OCR 화면. 기존 수동 ROI 장치 패널과 별개다. Vision LAB의 관측은 독립 실험 표시이며 이 작업에서 서버 최종 판정으로 자동 전송하지 않는다.

Vision 소스는 별도 Vision 작업 폴더에서 가져왔고, 학습 데이터·모델·실험 결과와 원본 작업 폴더는 그대로 보존했다. 학습 모델은 `RADAR_VISION_ROOT`(기본 `~/Desktop/Boeing_RADAR-vision`)의 `vision/checkpoints/mcp_ocr_v3`를 참조한다. OCR 서버는 loopback 8766에서 실행한다. 모델/캡처를 Git에 추가하지 않는다.

기존 ZIP 서버 5178/8018 및 DB를 변경하지 않는다. 현재 프로젝트 서버 5179/8019는 재시작했으며 기존 `.demo/zip-ai.db`를 유지한다. 통합 전 미커밋 소스 백업은 `.demo/pre-zip-integration.zip`이다.

운영 패널 자동 영역 수정: 5179의 운영 화면에서도 카메라 미리보기 연결 후 **Vision AI 자동 인식 시작**을 누르면 ALT·HDG 창을 자동 탐색한다. 수동 드래그는 제거했다. 자동 탐색은 보존한 Vision 영역 탐색기를 사용하고, 숫자 판독은 ZIP의 Apple Vision OCR을 사용해 기존 서버 판정으로 전송한다. 탐지 실패 시 보류하며 이전 영역을 재사용하지 않는다. 원본 ZIP 5178 화면에는 이 수정이 없다.
