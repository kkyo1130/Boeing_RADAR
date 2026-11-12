# 모의 3D MCP 카메라 수집 동기화

사용자 요청 범위: 수집용 모의 화면의 HDG/ALT만 제어한다. OCR 예측은 정답으로 사용하지 않는다.

## 실행

프로젝트 루트의 터미널 두 개에서 실행한다.

```sh
cd frontend
npm run dev
```

태블릿에서 `http://<Mac LAN IP>:5173/cockpit?display=tablet`을 열고 MCP 정면을 선택한다.
Mac IP는 `ipconfig getifaddr en0`으로 확인한다. 태블릿 화면을 켜고 해당 탭을 전면에 유지한다.
`display=tablet`은 카메라가 촬영하는 브라우저 한 개에서만 사용한다. Mac 미리보기에는 `/cockpit`만 사용한다.
수집용 display 모드에서는 숫자 터치/버튼 조작을 잠근다. 일반 화면 수동 조작은 유지한다.

```sh
source .venv/bin/activate
python vision/collect_camera_mcp.py --source 0 \
  --output "vision/data/camera_batches/sync_$(date +%Y%m%d_%H%M%S)" \
  --display-id tablet --preset-plan --auto-interval 0
```

학습된 YOLO MCP 탐지를 쓰려면 기존 `--yolo-weights <best.pt>` 옵션을 추가한다.
기본 OpenCV 탐지와 전처리 경로도 유지한다. 자동 촬영은 `--auto-interval 0.6`을 사용한다.

- 초기값 270/03000부터 시작하며 지정한 8조합 순서로 각 15쌍씩 수집한다.
- READY 표시 후 SPACE로 저장한다. 각 15쌍에서 저장이 멈추면 N → Enter로 다음 조합을 요청한다.
- 일반 수동 입력은 `--preset-plan`을 빼고 `--pairs 120`을 사용한다. N → M → HDG/ALT 입력.
- N → R은 현재 값을 재전송한다. Q 또는 Esc는 종료한다.
- labels.csv에는 선행 0을 포함한 문자열 정답을 기록한다. Excel 등에서 숫자로 자동 변환하지 않는다.
- 출력 폴더는 매 실행 새 타임스탬프로 생성한다. 기존 배치를 삭제하지 않는다.

## 프로토콜과 실패 처리

Vite 개발 서버의 `/api/mcp-auto/set`, `/state`, `/ack` 로컬 HTTP를 사용한다.
서버 재시작마다 충돌하지 않는 UUID 명령 ID와 대상 display ID, HDG/ALT를 대조한다.
선택된 브라우저에서 Three.js 숫자 CanvasTexture를 갱신하고 실제 render 호출을 마친 프레임만 ACK한다.
GLB 미로딩, WebGL context loss, 배경 탭, 렌더 중단에는 새 ACK가 없다.
ACK는 1.2초 후 만료한다. Python은 전처리 전후 서버 상태를 확인하고, 연속 유효 상태 1초 안정화 후 저장한다.
연결 실패/다른 명령/잘못된 대상/미ACK는 차단한다. N 입력 중에는 촬영 루프가 멈춘다.
대기 중에도 카메라 프레임을 계속 읽는다. 실제 물리 디스플레이 출력/카메라 드라이버 버퍼까지 소프트웨어 ACK로 증명할 수는 없으므로 촬영 전 실제 화면을 확인한다.
태블릿 단절 탐지는 ACK 만료까지 최대 1.2초이며 Mac-서버 요청 실패는 해당 저장 시도부터 차단한다.
프로덕션 preview에는 이 개발용 API가 없다. 반드시 npm run dev로 실행한다.

## 잘못된 배치 삭제

자동 삭제하지 않는다. 아래 `<사용자가 확인한 배치 이름>`을 실제 삭제할 단일 폴더 이름으로 바꾸고 내용을 확인한 후 실행한다.

```sh
ls -la vision/data/camera_batches/<사용자가 확인한 배치 이름>
rm -ri vision/data/camera_batches/<사용자가 확인한 배치 이름>
```

## 검증과 인수

자동 검증 명령: `cd frontend && npm test && npm run build`,
`cd vision && python3 -B -m unittest test_mcp_display_sync -v`.
정확한 대상/값/명령 ACK, 만료, 재시작, 연결 실패, 안정화, 범위 검사를 포함한다.
실물 인수: 태블릿에서 120/05500 변경 → READY → SPACE → CSV 두 행/이미지 확인 → N 다음 값 반복.
태블릿 Wi-Fi 차단/탭 숨김 후 ACK 만료로 SYNC BLOCKED, Mac 서버 종료 시 저장 차단을 확인한다.
물리 태블릿·웹캠 촬영 120쌍과 실제 YOLO 추론은 자동 테스트와 구분하여 미실행으로 남긴다.

구현 파일: collect_camera_mcp.py, mcp_display_sync.py, CockpitVision.jsx, Cockpit3D.jsx,
mcpAutoControl.js, mcpAutoPlugin.js와 관련 테스트. main.jsx는 기존 /cockpit 경로를 유지하여 수정 불필요.
자체 리뷰: OCR 값의 정답 유입 없음, 구형 ACK 재사용 차단, 일반 화면 ACK 불가, 저장 직전 재확인.
기존 사용자 untracked 파일과 데이터는 보존. 현재 사용자 브랜치의 미커밋 변경이며 외부 리뷰/PR 제출은 미실행.

### 이번 실행 결과

- frontend `npm test`: 58 passed (신규 프로토콜 2건 포함).
- frontend `npm run build`: 성공, 기존 대형 번들 경고 있음.
- vision `python3 -B -m unittest test_mcp_display_sync -v`: 2 passed.
- 실제 임시 Vite HTTP 서버: 120/5500 설정, 잘못된 display ACK 400,
  정확한 ACK ready, 1.25초 후 ACK 만료 차단 확인 (브라우저 대신 합성 ACK).
- 실제 브라우저 WebGL 렌더·태블릿·카메라·CSV 촬영 인수는 미실행.
- 이 체크아웃에는 루트 .venv가 없어 Python 테스트는 시스템 python3/표준 라이브러리로 실행.
