# SPEC-001: 개발 환경과 모노레포 실행

## 기본 정보

- 요구사항 버전: 1
- 상태: draft (목표 초안; 현재 구현과 미정 사항은 별도 표시)
- Priority: P0
- 근거: [서비스 방향](../service/overview.md), [요구사항 매핑](../service/requirements-map.md)
- 기능 전체 검증: SPEC-001-WI-03 (SPEC-010은 서로 독립된 두 선택 기능이므로 각 WI 자체 검증)

## 목적과 범위

기존 서버를 보존하고 파트별 실행·검증 방법을 재현한다.

포함 범위는 아래 workitem의 산출물이다. 실제 항공기 제어·QNH/Baro와 다른 기능의 소유 계약은 제외한다. 2026-10-16 사용자 요청으로 WI-02 설치·설정·버전 관리와 WI-03 자동 검증 기반을 구현한다. 제품 기능 확장은 이 스펙의 범위 밖이다.

## 동작·계약·미정 사항

공통 단위·ID·시각·null·품질·근거는 [SPEC-002](002-observation-contracts.md), 판정은 [SPEC-005](005-safe-validation.md)를 따른다. 해당 계약 확장 전 현재 API가 지원한다고 가정하지 않는다.
미정 사항 Q-01~Q-05와 영향 범위는 [서비스 방향](../service/overview.md#결정이-필요한-항목)에 있다. workitem의 선행 결과와 필수 결정이 확보된 범위만 구현한다. fixture 성공과 실카메라·마이크·수신 성공을 구분한다.

## 완료 조건

| ID | 입력·전제와 관찰 가능한 기대 결과 | 검증 | 담당 workitem |
| --- | --- | --- | --- |
| AC-01 | 선행: 없음. 기존 26개 파일 내용 보존, backend 테스트 17개 통과, 실제 서버 정상·오류 수정 흐름 성공 | 파일 내용 비교·pytest·임시 DB HTTP 시연 | [SPEC-001-WI-01](#wi-01) |
| AC-02 | 선행: SPEC-001-WI-01. 실제로 구현된 파트만 설치·실행·검증 명령과 설정 예제를 제공하고 새 환경에서 재현한다 | 지원 환경에서 새 가상환경/의존성 설치·기본 실행; 버전 정책은 각 도구 선택 후 결정 | [SPEC-001-WI-02](#wi-02) |
| AC-03 | 선행: SPEC-001-WI-02. 기존 backend 회귀와 구현된 계약 검사를 재현 가능하게 실행하고 하드웨어 검증을 별도로 표시한다 | CI 또는 로컬 재현; 실제 하드웨어 결과를 자동 테스트 통과와 혼동하지 않는지 확인 | [SPEC-001-WI-03](#wi-03) |

## Work items

진행 상태의 원본은 [TODO](todo.md)다. 아래 담당자는 기획 역할 기준 제안이며 작업 예약은 아니다.

<a id="wi-01"></a>

### SPEC-001-WI-01: 기존 서버 이동과 디렉터리 골격

- Priority: P0; 담당 제안: 공통
- 완료 조건: AC-01
- 선행 작업·산출물: 없음
- 수정 영역: `backend/ 및 루트`
- 산출물·개별 완료 조건: 기존 26개 파일 내용 보존, backend 테스트 17개 통과, 실제 서버 정상·오류 수정 흐름 성공
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 파일 내용 비교·pytest·임시 DB HTTP 시연
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

- 코드 기준: `8a05c1c` (`codex/monorepo-scaffold`, origin에 푸시됨). 구조 변경은 PR #2로 dev(`436c90c`)에 병합됨. main은 기존 PoC(`e0a290d`)이며 문서 계획은 미커밋.
- 수행 근거: 사용자 요청으로 구조 생성·기존 코드 이동·테스트·커밋/푸시 완료.
- 검증: 기존 26개 파일과 origin/dev 바이트 비교 일치. `cd backend && .venv/bin/python -m pytest -q`: 17 passed, 1 Starlette deprecation warning.
- 실제 로컬 HTTP: 임시 SQLite에서 Uvicorn 시작, Swagger, 11개 엔드포인트, 정상·Readback/Setting 오류 수정·종료·23개 Trace 이벤트 확인. 일회성 시연 스크립트는 저장소에 포함하지 않았으며 상시 자동 검증 산출물은 WI-03에서 준비한다.
- 리뷰: 코드 이동은 100% rename, 문서 실행 경로 수정 확인. 별도 에이전트 리뷰는 수행하지 않음.
- 남은 일: 다른 파트는 골격이며 WI-02의 실행 환경을 구현할 때 도구 버전·설정을 결정한다.

<a id="wi-02"></a>

### SPEC-001-WI-02: 파트별 실행·설정·버전 관리

- Priority: P0; 담당 제안: 공통
- 완료 조건: AC-02
- 선행 작업·산출물: SPEC-001-WI-01
- 수정 영역: `README.md, scripts/, 각 파트 의존성`
- 산출물·개별 완료 조건: 실제로 구현된 파트만 설치·실행·검증 명령과 설정 예제를 제공하고 새 환경에서 재현한다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 지원 환경에서 새 가상환경/의존성 설치·기본 실행; 버전 정책은 각 도구 선택 후 결정
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

- 구현: 2026-10-16 사용자 요청으로 `.python-version`, `.node-version`, `backend/.env.example`, `requirements-dev-py313.lock`, `scripts/bootstrap.py`, `docs/development/README.md` 추가. Frontend engines/engine-strict·lockfile 메타데이터와 파트별 README 갱신. Python 3.13 테스트 의존성 constraints, Node 24 기준/npm ci를 명시. 기본 설치는 Backend+Vision test/capture+Frontend이며 통신 골격의 가짜 실행 명령은 만들지 않음. `python` 브랜치 `7c95feb` 기준 미커밋.
- 검증: 빈 임시 가상환경에서 `python3 scripts/bootstrap.py --venv /private/tmp/radar-fresh-validation` 설치 성공(Python 3.13.7, Node 24.18.0, npm 11.16.0). Frontend 별도 임시 복사본도 node_modules 없이 npm ci·빌드 통과. 설치된 Vision CLI 3개 --help, 실제 Vite 시작/index·JSX HTTP 200 확인. macOS Swift OCR 새 컴파일 후 합성 이미지 평가 5개 기대 사례 통과, 흐림 1개는 채점 제외 유지. 실제 loopback Backend의 정상/두 오류/수정/종료/Trace 확인. 네트워크/포트/OCR 샌드박스 제한은 명시 권한으로 재실행해 해결. 원본 녹음/영상·실카메라/마이크/SDR·브라우저 E2E·Linux/Node22 새 환경은 미실행.
- 리뷰: 단일 에이전트가 역할 지침 적용. 환경 파일은 자동 로드한다고 주장하지 않음. 개발/검증 DB를 분리하고 출력·원본·키를 추가하지 않음. Python 3.13 lock에는 개인 절대 경로나 editable 로컬 경로를 기록하지 않음. 참조 minor 밖은 선언 범위 해결임을 명시. 기존 사용자 코드·브랜치 보존.
- 인수인계: [개발 환경 안내](../development/README.md)의 설치→검증→개별 실행 순서 사용. 전체 자동 결과는 WI-03 참조. 런타임 자체는 설치 스크립트가 준비하지 않으므로 Python/Node를 먼저 설치한다. 커밋·푸시·PR 갱신 미실행.

<a id="wi-03"></a>

### SPEC-001-WI-03: 자동 검증 기반과 공유 개발 안내

- Priority: P0; 담당 제안: 공통
- 완료 조건: AC-03
- 선행 작업·산출물: SPEC-001-WI-02
- 수정 영역: `scripts/, tests/integration/, CI 설정`
- 산출물·개별 완료 조건: 기존 backend 회귀와 구현된 계약 검사를 재현 가능하게 실행하고 하드웨어 검증을 별도로 표시한다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: CI 또는 로컬 재현; 실제 하드웨어 결과를 자동 테스트 통과와 혼동하지 않는지 확인
- 기능 전체 검증: 예; 이 스펙의 모든 AC를 대조하되 환경과 mock/실입력을 구분한다.

#### 결과·검증·리뷰·인수인계

- 구현: `scripts/verify.py`, `scripts/smoke_backend.py`, `.github/workflows/verify.yml` 및 공유 개발 안내 추가. Backend/계약/통합, Vision, Frontend 빌드와 선택 실제 HTTP 시연을 한 명령으로 실행. CI는 Ubuntu/macOS Python 3.13 및 Ubuntu Node24로 구성. 공식 Action 문서와 YAML 구조 확인. 기존 WI-01 회귀와 계약 검사 포함, 하드웨어 검증은 별도 표시.
- 검증: `python3 scripts/verify.py --python /private/tmp/radar-fresh-validation/bin/python --http-smoke`: Backend/계약/통합 **195 passed, 1 warning**(Starlette/httpx deprecation), Vision **45 passed**, 실제 HTTP 시연·Frontend 빌드 통과. 공통 실행의 개발 DB는 임시 경로로 강제. 누락 Python은 exit 1, backend 없이 --http-smoke는 exit 2 및 PASS 미출력 확인. 초기 venv 실행 파일을 resolve해 시스템 Python으로 바뀌던 문제는 absolute로 수정하고 전체 명령으로 재검증. 스크립트 구문·lockfile engines 일치·CI YAML 구조·문서 링크·git diff --check 통과.
- 리뷰: 단일 에이전트가 역할 지침 적용. 전체 선택 검사 통과 전 PASS를 출력하지 않고 실패 코드를 전파함. 실제 HTTP는 임시 DB/127.0.0.1 서버만 사용하고 종료 후 정리. CI는 pull_request_target 없이 contents:read, checkout 자격 증명 저장 비활성화. Linux OpenCV 공유 라이브러리 설치 포함. 자동화 범위를 모델/장비 검증으로 표현하지 않음.
- 인수인계: SPEC-001 AC-01은 기존 이동 검증 근거와 이번 전체 회귀/HTTP, AC-02는 WI-02 새 설치·기본 실행, AC-03은 공통 명령·실패 전파로 대조 완료. GitHub 원격 CI job은 아직 미실행이며 원격 통과를 주장하지 않음. 실장비·브라우저 조작·실제 생산자 어댑터는 후속 기능의 인수 범위다. `python` 브랜치 `7c95feb` 기준 미커밋, 커밋·푸시 미실행.

## 변경 기록

- v1 · 2026-10-10: 사용자 제공 기획·Priority·자문과 현재 코드로 최초 작업 초안 작성. 문서 작성 권한과 기능 구현 권한은 구분한다.

- 2026-10-16: WI-02/03 설치·버전·설정 및 로컬/CI 검증 기반 구현. 새 macOS 환경과 공통 명령 검증 완료; 원격 CI/실장비는 별도.

2026-10-17 커밋 인수인계: 사용자 요청으로 기능별 커밋에 보존했다. 앞선 미커밋 표기는 당시 기록이며 코드 커밋과 재검증 근거는 [단계별 커밋 기록](todo.md#2026-10-17-단계별-커밋-기록)을 따른다. 실제 인수 미실행 상태는 유지한다.
