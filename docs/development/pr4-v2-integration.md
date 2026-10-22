# PR #4: v2 통합 기록

2026-10-22 사용자 요청: kkyo1130의 PR #4와 dev의 기능 중복을 정리하고 PR을 병합한다. 이번 작업은 새 WI 일괄 구현이 아니라 기존 PR의 통합 수정이다.

## 기준과 최종 구조

- dev: `75e74acc7b4969dc822e393c33aff6ac8de832f8`
- 원래 PR #4/python: `9380807204df4319affa30af57719566b8be2a87` (이미 위 dev를 포함).
- 기존 `/operations`, `/api/v2`, 구조화/3상태/사건/음성 정책을 유지한다. 기존 판정 엔진을 다시 구현하지 않는다.
- `/operations-v1`, `/api/v1`, contract_* 모델, v1 판정·사건 엔진과 해당 전용 테스트/fixture는 제거했다. v2 회귀 테스트는 유지하고 추가 기능의 v2 회귀를 작성했다. 제거 전 코드는 원래 PR 커밋에 보존된다.
- 기존 spec/WI 진행 상태를 dev 기준으로 보존했다. v1 구현 완료 기록으로 v2 작업 완료를 덮어쓰지 않는다. 실제 장비 인수도 자동 완료 처리하지 않는다.

## 파일별 변경

- `backend/app/models/operations_v2.py`: v2 비행에 귀속된 media와 frozen report만 추가. 관측·사건·판정 저장소는 기존 것을 사용한다.
- `backend/app/services/media_v2.py`, `api/operations_v2.py`: PNG/JPEG/PCM WAV bytes 검사, 크기 제한, 업로드/삭제와 Trace. 선택한 근거의 소유 비행을 검사하며 원본 삭제는 과거 관측을 지우지 않는다.
- `services/evidence_v2.py`: 기존 패널/범위 검사/Range 응답에 저장된 media 참조를 연결. 기존 `media:` 로컬 근거 경로도 유지.
- `services/reports/v2.py`, `services/receiving_v2.py`: END 트랜잭션에서 마지막 라이브 판정과 종료 Trace를 고정. `/state`는 기존처럼 종료 후 UNVERIFIED. 리포트 집계는 v2 데이터만 조회한다.
- `frontend/src/ReportPanel.jsx`: 기존 Operations에 종료 요약/JSON 다운로드를 추가. 기존 화면은 컴포넌트 연결 2줄만 추가했으며 별도 운영 화면·TTS를 만들지 않는다.
- `scripts/produce_observation.py`: 기존 v2 문법 파서를 재사용하고 등록된 segment/attempt/ATC 연결을 통해 수신한다. 보조 음성 중단 확인 후 입력 시작, 실패 시 입력 token 정리. 한 발화 30초 초과는 잘라서 지시로 채택하지 않고 거부. 시각 미상/불완전/품질 미확인은 보류.
- `communication/radar_audio`, `services/speech/local.py`: PR의 PCM 처리/마이크/로컬 Whisper는 유지. 중복 숫자/판정 함수는 제거.
- Vision 전송은 원래 frame/시각/health를 유지하고 캡처 이전 target_revision을 사용한다. 새 지시 후 기존 revision으로 처리하면 보류되므로 새 캡처/어댑터 revision이 필요하다.
- PR의 평가 도구·개발 bootstrap·CI는 유지. verify에 기존 frontend 단위 테스트 실행을 추가. demo/E2E는 v1 대신 실제 v2 API를 검증한다.

## 검증

실행 환경: Linux, Python 3.12.14(요구 범위 설치), Node 24.19.0. Python 3.13 constraints 재현 및 macOS CI 실행은 이번 환경에서 수행하지 않았다.

- `python3 scripts/bootstrap.py --skip-frontend`, frontend의 `npm ci`: 설치 성공.
- `.venv/bin/python scripts/verify.py --component backend --component vision --http-smoke`: **backend/HTTP 통합 522 passed**, **Vision 45 passed**, legacy HTTP 정상/두 오류/수정/종료 및 v2 HTTP 정상/복창 오류/설정 오류/판독 불가/새 관측 해결/리포트 출력 통과.
- `.venv/bin/python scripts/verify.py --component frontend`: **39 passed**, Vite production build 통과.
- frontend에서 `RADAR_CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e`: **2 passed**. 실제 v2 HTTP 서버 + Chromium으로 시작→정상→설정 불일치→업로드 근거 열람→사용자 확인→새 관측 해결→연결 끊김/복구→종료 리포트와 MCP 화면 유지 확인.
- `test_operations_v2.py`: 마지막 라이브 정상의 종료 보존, 종료된 현재 상태는 보류, 재조회/시간 경과 후 리포트 불변, JSON export, 기존 근거 패널 연결, 비행 간 삭제 거부, 삭제 뒤 410/관측 보존, 불량 업로드 및 종료 후 업로드 거부, v1 route 제거.
- `test_producer_adapters.py`: mock ASR의 v2 채택과 시각 미상 보류, Vision 정상/영상 시각 미상, health 원시각 보존, 입력 실패 정리, v2 문법 재사용, 과거 revision의 새 지시 연결 거부.
- 기존 v1 전용 테스트 수를 v2 통과 수에 합산하지 않았다. 첫 시연 실패는 fixture의 기본 HDG=0을 목표 270으로 맞추지 않은 테스트 구성 오류였다. 브라우저 첫 실패도 v2 화면의 실제 selector/문구(`일치`)와 다른 테스트 기대값을 수정했다. 제품 판정이나 기존 assertion을 완화해 통과시키지 않았다.

## 리뷰와 남은 제약

단일 에이전트 코드 검토: 중복 엔진 제거, v2 데이터 소유권, 파일 형식/크기/삭제, 종료 트랜잭션, 원본 시각·새 관측, 입력 우선순위, 기존 화면 유지와 CI 명령을 확인했다. 외부 리뷰 완료를 주장하지 않는다. Starlette/httpx 사용 중단 예정 경고 1개는 기존 테스트에서 발생하며 실패가 아니다.

실제 카메라·마이크·스피커·Whisper 모델 성능·SDR은 미검증이다. 브라우저 다운로드 도메인이 차단되어 설치된 Chromium을 사용했다. GitHub API도 차단되어 PR 설명/댓글/원격 CI 상태를 확인하거나 편집하지 못한다. Git HTTPS 접근과 브랜치 ref를 사용하며 보호 규칙을 우회하지 않는다.

DB는 추가 테이블만 생성하고 과거 v1 데이터를 자동 삭제/변환하지 않는다. 기존 v1 기록의 이관은 별도 작업이다. 업로드는 신뢰하는 로컬 실험 환경용이며 인증/자동 보존기간 삭제는 이번 범위 밖이다. 원본 파일 삭제 이후 frozen report는 당시 참조를 보존하고 현재 가용성은 media 응답과 삭제 Trace로 판단한다.

실행 명령과 공개 API는 [운영 안내](operations.md)를 따른다.
