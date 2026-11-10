# Vision AI Implementation Plan

> Issue: [#30 — Boeing 737 MCP ALT·HDG 인식 및 RADAR API 연동](https://github.com/kkyo1130/Boeing_RADAR/issues/30)
>
> Base: `dev` | Work branch: `feat/vision-ai` | PR target: `dev`
>
> Status: **Planning only** — no implementation or dataset has been committed.

## 1. 목표 및 범위

Boeing 737 MCP(Mode Control Panel)의 **설정 고도 ALT(ft)** 및 **설정 방위 HDG(°)**를 이미지 또는 웹캠 영상에서 인식해 기존 Boeing_RADAR의 Cockpit Observation API로 전달한다. 관제 지시(ATC), 복명복창(Readback), Cockpit 설정값의 비교와 Safety Trace 기록은 기존 FastAPI 백엔드가 담당한다.

- 입력: 정지 이미지 또는 실제 웹캠 프레임
- 출력: `altitude: int >= 0`, `heading: int 0..359`, 평가·보정된 `confidence: float 0..1`, 관측 시각
- 지원 기종(1차): Boeing 737 MCP
- 별도 보관/향후 평가: Airbus A300-600R 실제 조종석 사진
- 제외: 3D 조종석 시뮬레이터 제작, STT, 실제 항공 운항용 인증 및 안전 판정

**원칙:** 시뮬레이터의 내부 설정값을 직접 읽지 않는다. 실제 카메라 영상에서 추출한 값만 API로 전송한다.

## 2. 현재 저장소 연동 지점

현재 `app/schemas/observation.py`의 `ObservationInput`은 `altitude`, `heading`, `confidence`를 요구하고 `transcript`, `observed_at`를 선택적으로 허용한다. `confidence`는 현재 백엔드의 일치 비교에 반영되지 않는다.

- 최초 설정값: `POST /api/clearances/{clearance_id}/cockpit`
- 설정 오류 수정: `POST /api/clearances/{clearance_id}/cockpit/reverify`
- 현재 상태 확인: `GET /api/clearances/{clearance_id}`
- 기록 확인: `GET /api/flights/{flight_id}/safety-trace`

`/cockpit`은 Readback이 먼저 입력되어야 하며, 중복 최초 입력과 잘못된 재검증 순서는 409를 반환한다. Vision 어댑터는 Clearance 상태를 확인하고 수동 확인 또는 안정화 조건 충족 시에만 전송한다. 인식 실패는 설정 불일치로 간주하지 않는다.

## 3. 데이터셋 확보 및 관리

### 3.1 실제 Boeing MCP 공개 사진
- Wikimedia Commons 등 출처/사용 조건을 확인할 수 있는 자료부터 조사한다.
- 수집 전 이미지별 라이선스, 저작자, 원본 URL, 이용 조건 및 학습/배포 가능 범위를 검토한다.
- ALT·HDG 표시가 읽히는 사진을 우선 선별하고, 각 이미지에 실제 숫자와 촬영 조건을 라벨링한다.
- **목표:** 초기 50~100장(가용성과 라이선스에 따라 변경). 미확보 사진을 확보된 것처럼 간주하지 않는다.
- 원본 사진은 사용 권한을 확인하기 전 GitHub에 업로드하지 않는다.

### 3.2 직접 생성한 합성 데이터
- 직접 제작한 MCP 스타일 패널에 ALT·HDG 숫자를 렌더링한다. 제3자 사진을 허가 없이 편집해 합성하지 않는다.
- 고도·방위 조합, 글꼴/표시 스타일, 밝기, 색온도, 원근, 블러, 노이즈, 반사, 크롭을 다양화한다.
- 생성과 동시에 숫자 정답, 이미지 경로, 랜덤 시드, 생성 파라미터를 CSV/JSON으로 기록한다.
- **목표:** 초기 500~1,000장. 실제 패널과의 도메인 차이를 별도 검증한다.

### 3.3 실제 웹캠 촬영
- 팀이 모니터에 MCP 시뮬레이션 화면을 표시하고 실제 웹캠으로 촬영한다.
- 거리, 각도, 초점, 반사, 화면 밝기 및 숫자 조합을 변화시킨다.
- **목표:** 초기 100~200장. 카메라 접근이 없는 개발 환경에서는 촬영 스크립트만 준비한다.
- 같은 촬영 세션의 연속 프레임은 학습/검증/테스트에 걸쳐 섞지 않는다.

### 3.4 Airbus A300-600R
- 견학 시 사진 촬영 및 AI 학습/발표 활용 허가를 확인한다.
- `airbus_a300/`에 별도 보관하며 Boeing 737 초기 학습에 혼합하지 않는다.
- 추후 기종 간 일반화 성능 평가 또는 별도 기종 인식 확장에 사용한다.

### 3.5 데이터 구조(예정)
```text
vision/data/
├── boeing_737/
│   ├── raw/
│   ├── synthetic/
│   ├── webcam/
│   └── labels.csv
└── airbus_a300/
    └── real_photos/
```
원본 이미지·대용량 가중치·개인/보안 민감 자료는 기본적으로 Git 추적에서 제외하고, 재현 가능한 생성 코드·메타데이터 스키마·사용 방법만 버전 관리한다.

## 4. 개발 단계

### Phase 1 — 데이터 수집 및 라벨링
- [ ] 이미지/웹캠 캡처 도구
- [ ] 공개 사진 출처·라이선스 기록 양식
- [ ] 합성 MCP 이미지 및 자동 라벨 생성기
- [ ] 세션 기준 train/val/test 분리 스크립트

### Phase 2 — 인식 베이스라인
- [ ] OpenCV 전처리: 크롭, 대비, 노이즈, 원근 보정
- [ ] 고정 카메라 환경의 수동 ROI 설정 및 ALT/HDG 분리
- [ ] 사전학습 OCR로 숫자 인식
- [ ] 선행 0을 포함한 HDG 3자리 처리, ALT 정수 및 범위 검증
- [ ] 미검출/불확실 상태 반환(임의 숫자 채우기 금지)

### Phase 3 — 평가 및 선택적 학습
- [ ] ALT 정확도, HDG 정확도, **동시 정확도** 및 실패율 측정
- [ ] 실제 사진·합성 이미지·웹캠 테스트 결과 분리
- [ ] 필요시 OCR 파인튜닝 및 학습 체크포인트 관리
- [ ] ROI 고정 방식이 실패할 경우에만 패널 탐지 모델(YOLO 등) 학습 검토
- [ ] 목표: 시연 환경 동시 정확도 95% 이상(측정 전 목표일 뿐 성능 보장 아님)

### Phase 4 — 실시간 인식 및 API 연동
- [ ] 카메라 프레임 표시, 인식 영역 및 결과 오버레이
- [ ] 여러 프레임 일치/신뢰도 안정화, 중복 전송 방지
- [ ] 수동 승인 모드와 자동 전송 모드 분리
- [ ] `/cockpit`, `/cockpit/reverify` 상태 기반 전송
- [ ] 404/409/422 및 서버 연결 오류 처리, 재시도 시 중복 제출 방지
- [ ] 인식 실패 시 전송 보류 및 재촬영 안내

### Phase 5 — 테스트 및 문서화
- [ ] 합성 입력 기반 단위 테스트(숫자 변환, 범위, 저신뢰 보류)
- [ ] Mock API 연동 테스트(최초 입력/설정 오류/재검증)
- [ ] 기존 `pytest` 회귀 테스트
- [ ] 카메라 실행, 데이터 준비, 학습 및 평가 명령 문서화

## 5. 예상 코드 구조

```text
vision/
├── config.py
├── capture.py
├── preprocess.py
├── detector.py
├── recognizer.py
├── pipeline.py
├── confidence.py
├── api_client.py
├── run_camera.py
├── evaluate.py
├── train_ocr.py
├── train_detector.py
└── data/                  # 데이터 파일은 기본적으로 Git 제외
tests/
├── test_vision.py
└── test_vision_integration.py
requirements-vision.txt
docs/VISION_AI.md
```

구체적인 OCR 및 학습 라이브러리는 베이스라인 실험 결과를 바탕으로 확정한다. 학습 코드 구현과 학습 완료 모델 확보는 별개이다.

## 6. 완료 기준

1. 이미지와 실제 웹캠에서 ALT·HDG 인식 결과 및 실패 상태를 구분해 출력한다.
2. 정확도 평가가 재현 가능하고, 데이터 출처와 분할 기준이 문서화된다.
3. 저신뢰 인식 결과를 임의 설정값으로 API에 전송하지 않는다.
4. 기존 API를 통해 `SETTING_ERROR` 및 `RESOLVED` 시나리오가 통과한다.
5. 기존 백엔드 테스트가 통과하며, `dev` 대상 PR에서 리뷰할 수 있다.

## 7. 작업 순서 및 주의사항

- 우선 데이터 수집/생성 파이프라인과 사전학습 OCR 베이스라인을 구현한다.
- 실제 웹캠 촬영 및 실제 사진의 라이선스 확인은 별도 입력/승인이 필요하다.
- 모델 파인튜닝 및 YOLO는 베이스라인의 실패 유형을 확인한 뒤 진행한다.
- 본 계획 문서는 구현 확정 사항이 아닌 작업 가이드이며, 결과는 테스트로 검증한다.
