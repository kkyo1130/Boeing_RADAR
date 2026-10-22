# 개발 환경과 공통 검증

SPEC-001-WI-02/03의 설치·설정·실행 기준이다. 실제 구현된 Backend, 태블릿 MCP Frontend, Vision만 설치한다. 로컬 음성은 --speech로 선택 설치한다. v2 입력/운영은 [운영 안내](operations.md)를 따른다.

## 버전과 설치

| 도구 | 기준 | 검증 범위 |
| --- | --- | --- |
| Python | `.python-version`: 3.13 | 로컬 새 환경 3.13.7; CI 기준 3.13 |
| Python 요구 최소 | 파트 메타데이터/스크립트 3.11+ | 3.11 새 환경은 이번에 미실행 |
| Node.js | `.node-version`: 24 | 로컬 24.18.0; CI 기준 24 |
| Node 허용 범위 | 22.x의 22.20 이상 또는 24.x의 24.12 이상 | frontend engines·engine-strict로 검사; 22.x 로컬 미실행 |
| npm | package-lock v3, npm ci | 로컬 11.16.0 |
| 플랫폼 | macOS / Linux CI | 실제 새 환경 재현은 macOS; Linux 원격 CI 실행은 별도 확인 |

버전 파일은 기준이며 런타임 자체를 설치하지 않는다. Python 3.13과 Node 24를 먼저 준비하고 저장소 루트에서 실행한다.

```sh
python3 scripts/bootstrap.py
python3 scripts/verify.py
```

bootstrap은 루트 `.venv`를 만들고 Backend 및 Vision의 test/capture 의존성을 설치한 뒤 Frontend에서 npm ci를 실행한다. 설치에는 네트워크가 필요하다. 기존 `.venv`가 있으면 재사용하며 삭제하지 않는다. Node가 없는 서버 전용 환경은 `--skip-frontend`를 사용한다.

Python 3.13은 검증한 런타임/테스트 의존성인 `requirements-dev-py313.lock`을 constraints로 적용한다. 각 파트 요구 범위는 backend/requirements.txt와 vision/pyproject.toml에 유지한다. 다른 Python minor 버전은 범위로 해결하며 동일 lock 재현을 주장하지 않는다. setuptools 빌드 의존성은 pyproject의 범위를 따른다. Frontend는 package-lock.json으로 고정한다. 버전 변경 시 새 환경 설치와 전체 검증 결과를 해당 WI/PR에 남긴다.

별도 환경을 만들 경우:

```sh
python3 scripts/bootstrap.py --venv /tmp/radar-dev
python3 scripts/verify.py --python /tmp/radar-dev/bin/python
```

## Backend 실행·설정

서버는 **backend 디렉터리 기준**으로 실행한다.

```sh
cd backend
export RADAR_DATABASE_URL=sqlite:///./radar.db
export RADAR_V2_CONFIG="$PWD/../contracts/examples/integration/config.json"
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs . DB 상대 경로는 실행 디렉터리 기준이다. backend/.env.example은 값의 예시이며 앱이 .env를 자동으로 읽지 않는다. 환경변수를 직접 export하거나 신뢰할 수 있는 로컬 파일을 셸에서 명시적으로 로드한다. 예시 config는 합성 검증용이며 안전/운용 기준이 아니다.

기존 DB는 앱 시작 시 v2 테이블을 추가한다. 명시 실행: backend에서 `../.venv/bin/python -m app.migrate_observation_v2 --database-url sqlite:///./radar.db`. 기존 테이블은 삭제하지 않는다.

실제 loopback HTTP와 임시 DB를 사용한 재현:

```sh
python3 scripts/smoke_backend.py
```

정상·두 오류·수정·종료·Trace를 확인하고 서버와 임시 DB를 정리한다. 기존 개발 DB를 사용하지 않는다. 로컬 포트가 허용된 환경에서만 실행되며 포트 바인딩/서버 시작 오류는 실패로 종료한다.

## Frontend 실행

```sh
cd frontend
npm run dev
```

주소는 http://localhost:5173/ . 기본 화면은 수동 태블릿 MCP, `/operations`는 v2 비행 운영 화면, 근거·종료 리포트도 같은 v2 화면에 포함한다. [운영·실입력 안내](operations.md)를 따른다. Vite는 LAN 접속을 위해 0.0.0.0:5173을 사용한다. 태블릿에는 PC의 LAN 주소를 입력한다. Node 엔진 범위를 벗어나면 설치가 실패한다. 빌드는 `npm run build`다. Vite `/api` 프록시 기본 대상은 127.0.0.1:8000이며 `RADAR_API_TARGET`으로 변경할 수 있다.

## Vision 실행

루트 `.venv` 설치에 OpenCV가 포함된다. 카메라 열기와 GUI ROI 선택은 별도 수동 검증이다. CLI 기본 실행은 다음으로 확인한다.

```sh
.venv/bin/radar-vision --help
.venv/bin/radar-vision-stream --help
.venv/bin/radar-vision-setup --help
```

실제 OCR 어댑터는 macOS Vision이며 Command Line Tools가 필요하다. Linux에서는 Python fixture 검사만 가능하다. 아래 컴파일·고정 합성 이미지 확인은 macOS에서 별도로 실행한다.

```sh
mkdir -p vision/.build
xcrun swiftc vision/native/ocr.swift -o vision/.build/radar-ocr
.venv/bin/python vision/evaluation/run.py --ocr-binary vision/.build/radar-ocr
```

이 평가는 합성 정지 이미지 회귀이며 실카메라 성능이 아니다. 정상 종료와 판독 성공도 구분한다. 촬영/ROI 설정·스트림 옵션은 [태블릿 안내](../../vision/docs/tablet-demo.md)를 따른다. 이미지 크기·ROI·단위와 실제 촬영 시각은 입력 자료에 맞춰 설정한다. 파일 수정 시각을 촬영 시각으로 사용하지 않는다.

## 자동 검증과 CI

```sh
python3 scripts/verify.py
python3 scripts/verify.py --http-smoke
python3 scripts/verify.py --component backend --component vision
python3 scripts/verify.py --component frontend
```

기본 실행은 Backend/계약/통합 pytest, Vision pytest, Frontend 빌드다. Backend 테스트의 기본 앱 DB도 임시 경로로 강제해 사용자 DB와 분리한다. 실패나 누락 의존성은 비정상 종료하고 통과 메시지를 출력하지 않는다. --http-smoke는 backend 선택 시에만 사용하며 실제 HTTP 시연을 추가한다.

[워크플로](../../.github/workflows/verify.yml)는 dev/main 대상 PR, 지정 브랜치 push, 수동 실행에서 같은 명령을 사용한다. Python fixture/HTTP 검사는 Ubuntu와 macOS, Frontend는 Ubuntu/Node 24에서 실행하도록 구성했다. 원격 job이 실제 실행·통과했는지는 GitHub에서 별도로 확인한다. 로컬 결과를 원격 CI 통과라고 기록하지 않는다.

별도 검증: 실카메라·마이크, 실제 STT/Vision 생산자, 네이티브 OCR 엔진 평가. Chromium fixture E2E는 frontend의 `npm run test:e2e`로 분리하고 CI에도 구성했다. 네이티브 OCR 합성 평가는 위 별도 명령을 사용한다. CI가 이 항목을 검증한 것처럼 보고하지 않는다. 새 팀원은 설치→공통 검증→파트 기본 실행→필요한 수동 장비 검증 순서로 수행하고 팀원의 변경을 덮어쓰지 않는다.

워크플로 Action 사용 근거: [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), [setup-node](https://github.com/actions/setup-node)의 공식 문서.
