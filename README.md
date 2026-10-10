# RADAR

개발 계획은 [spec.md](spec.md), 작업 상태는 [전체 TODO](docs/spec/todo.md), Claude/Codex 설정은 [에이전트 안내](docs/agent/README.md)에서 확인합니다.

MCP 사진·인식 결과·결과 JSON과 실행 방법은 [Vision PoC 문서](docs/vision/README.md)에서 확인합니다.

현재 구현 기능과 세부 동작은 [구현 기능 문서](docs/IMPLEMENTATION.md)에 정리되어 있습니다.

관제 지시(ATC), 조종사 복명복창(Readback), Cockpit 설정값을 하나의 Clearance로 연결하는 Python 3.11+ PoC입니다. FastAPI 앱 하나에서 ALT/HDG 정확 일치 비교와 Flight Session, Safety Trace 저장을 처리합니다. 실제 STT·Vision AI·SDR 대신 JSON Mock Observation을 입력합니다.

## 설치 및 실행

저장소 루트에서 `backend/`로 이동해 Python 3.11 이상으로 실행합니다. 통신은 골격입니다. 태블릿 MCP 화면은 [frontend 안내](frontend/README.md), Vision 촬영/ROI·스트림은 [태블릿 데모 안내](vision/docs/tablet-demo.md)를 따릅니다.

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger: http://localhost:8000/docs

SQLite는 `backend/`에서 실행할 경우 최초 앱 시작 시 `backend/radar.db`에 생성됩니다. `RADAR_DATABASE_URL=sqlite:///./other.db`로 경로를 변경할 수 있습니다. 모든 시간은 UTC ISO 8601로 저장합니다. 입력한 `observed_at`에 시간대가 없으면 UTC로 해석합니다. 생략하면 서버 시각을 사용합니다. 이벤트 timestamp는 서버 기록 시각이며, 과거 Observation 입력도 이벤트 순서를 바꾸지 않습니다.

## 디렉터리 구조

```text
Boeing_RADAR/
├── frontend/src/             # React 태블릿 MCP 화면 + 운영 화면 골격
├── backend/
│   ├── app/                  # 기존 FastAPI 서버
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/         # 기존 서비스 및 확장용 빈 디렉터리
│   │   └── api/
│   ├── tests/                # 기존 Python 테스트
│   └── requirements.txt
├── vision/                   # 정지 이미지·영상/웹캠 OCR·상태 감시
├── communication/            # 통신 파트 골격
├── contracts/                # 관측 결과 계약 초안·예제
├── tests/integration/        # 파트 간 통합 테스트 골격
├── scripts/                  # 실행·평가 스크립트 골격
├── docs/IMPLEMENTATION.md
├── README.md
└── .gitignore
```

models는 저장, schemas는 입력/응답 검증, services는 업무 규칙, api는 HTTP 연결을 담당합니다. Observation 최신값은 Clearance JSON 컬럼에 저장하고 과거 입력은 Safety Event의 observation에 보존합니다. 나중에 STT/Vision/통신 모듈은 같은 입력 API로 Observation을 전송할 수 있습니다.

## 주요 API

| 메서드 | 경로 | 기능 |
|---|---|---|
| POST | `/api/flights/start` | 비행 생성 (201) |
| POST | `/api/flights/{flight_id}/end` | 비행 종료 |
| GET | `/api/flights/{flight_id}` | 비행 조회 |
| POST | `/api/flights/{flight_id}/clearances` | ATC 지시 생성 (201) |
| GET | `/api/flights/{flight_id}/clearances` | 지시 목록 |
| GET | `/api/flights/{flight_id}/safety-trace` | 이벤트 시간순 조회 |
| GET | `/api/clearances/{clearance_id}` | 세 Observation, 상태, errors |
| POST | `/api/clearances/{clearance_id}/readback` | 복명복창 최초 입력 |
| POST | `/api/clearances/{clearance_id}/cockpit` | Cockpit 최초 입력 |
| POST | `/api/clearances/{clearance_id}/readback/reverify` | 복명복창 오류 수정 |
| POST | `/api/clearances/{clearance_id}/cockpit/reverify` | 설정 오류 수정 |

입력 공통 필드: `altitude`(0 이상 정수, feet), `heading`(0–359 정수, degrees), `confidence`(0–1). `transcript`, `observed_at`는 선택입니다. Source는 엔드포인트가 지정합니다. 잘못된 입력은 422, 없는 리소스는 404, 종료된 비행 변경/잘못된 순서/잘못된 재검증은 409입니다.

Flight ID는 `FLT-YYYYMMDD-NNN`, Clearance ID는 `CLR-NNN`입니다. SQLite 정수 키를 사용하며 번호는 전체 DB에서 증가합니다(날짜마다 초기화하지 않음). 종료 API는 중복 종료를 거부합니다. 변경과 해당 이벤트는 하나의 트랜잭션으로 저장합니다.

## 상태 머신

- ATC 생성 → `WAITING_READBACK`
- ATC와 Readback의 ALT 또는 HDG 불일치 → `READBACK_ERROR`
- Readback 일치, Cockpit 미입력 → `WAITING_COCKPIT`
- Readback 일치, Cockpit 불일치 → `SETTING_ERROR`
- 세 값 일치 → `VERIFIED`
- 오류 상태에서 해당 reverify API 호출 → `REVERIFYING` 이벤트 → 재비교 → 오류 상태 또는 `RESOLVED`

Readback 비교가 항상 우선입니다. 오류마다 필드별 이벤트와 `ALERTED` 이벤트를 남깁니다. 재검증은 `REVERIFYING`, `*_UPDATED`(Observation 스냅샷과 필드 변경 기록), 결과 이벤트를 남깁니다. `REVERIFYING`은 같은 트랜잭션 안에서 최종 상태로 바뀌므로 조회에서는 최종 상태가 반환됩니다.

요구사항 CASE 2에 따라 Readback 오류 수정은 Cockpit이 없어도 `RESOLVED`입니다. 이는 복명복창 오류의 해소를 뜻합니다. 이후 Cockpit을 입력하면 `VERIFIED` 또는 `SETTING_ERROR`로 다시 판정합니다. Cockpit이 이미 있으면 재검증 시 함께 비교하므로 설정 오류를 숨기지 않습니다.

## Mock Demo / API 테스트

Swagger에서 아래 순서대로 요청하거나 아래 Python 스크립트를 실행합니다. 서버가 실행 중이어야 합니다.

```sh
python - <<'PY'
import httpx

with httpx.Client(base_url="http://localhost:8000") as api:
    def post(path, data=None):
        response = api.post(path, json=data)
        response.raise_for_status()
        return response.json()

    good = {"altitude": 18000, "heading": 240, "confidence": 0.96}
    bad = dict(good, altitude=16000)
    flight = post('/api/flights/start')['flight_id']
    def clearance():
        return post(f'/api/flights/{flight}/clearances', good)['clearance_id']

    # CASE 1: ATC 18000/240 → Readback 18000/240 → Cockpit 18000/240
    c = clearance()
    post(f'/api/clearances/{c}/readback', good)
    assert post(f'/api/clearances/{c}/cockpit', good)['status'] == 'VERIFIED'
    print('CASE 1 VERIFIED')

    # CASE 2: Readback 16000/240 → 수정 18000/240
    c = clearance()
    assert post(f'/api/clearances/{c}/readback', bad)['status'] == 'READBACK_ERROR'
    assert post(f'/api/clearances/{c}/readback/reverify', good)['status'] == 'RESOLVED'
    print('CASE 2 READBACK_ERROR → RESOLVED')

    # CASE 3: Cockpit 16000/240 → 수정 18000/240
    c = clearance()
    post(f'/api/clearances/{c}/readback', good)
    assert post(f'/api/clearances/{c}/cockpit', bad)['status'] == 'SETTING_ERROR'
    assert post(f'/api/clearances/{c}/cockpit/reverify', good)['status'] == 'RESOLVED'
    print('CASE 3 SETTING_ERROR → RESOLVED')

    response = api.get(f'/api/flights/{flight}/safety-trace')
    response.raise_for_status()
    for event in response.json():
        print(event['id'], event['event_type'], event['field'], event['timestamp'])
    assert post(f'/api/flights/{flight}/end')['status'] == 'ENDED'
    print('FLIGHT ENDED')
PY
```

## pytest

설치 및 실행과 마찬가지로 `backend/`에서 실행합니다.

```sh
python -m pytest -q
```

테스트별 임시 SQLite DB를 사용합니다. Flight 생성/종료, ALT/HDG 오류, 오류 수정, 비교 우선순위, 이벤트 순서와 입력 이력, Clearance 간 분리, 입력값 및 상태 제약을 검증합니다.

## TODO / 범위

향후 STT·Vision·통신 어댑터, 판단 보류·입력 건전성·근거 제공·재검증 및 리포트를 구현합니다. 상세 범위는 [스펙](spec.md)을 따릅니다. 자문 반영으로 QNH/Baro와 기압 센서 Sensor Cross-Check는 이번 범위에서 제외합니다. 백엔드는 P0 Mock 흐름이며 Vision은 정지 이미지·영상/웹캠 OCR·상태 감시·안정화, frontend는 태블릿 MCP 수동 화면까지 구현했습니다. 서버 통합과 실제 태블릿 촬영 검증은 남아 있습니다. 운영 도입에는 인증, 마이그레이션, 병렬 변경의 충돌 제어가 추가로 필요합니다. 항공 운용 판정용으로 검증된 시스템은 아닙니다.
