# 2026-11-18 dev 통합 검증

## 범위와 기준

사용자의 열린 PR 전체 반영 요청으로 PR #36–#51과 #15를 통합한다. 새 기능 목록의 추가 구현은 포함하지 않는다.

- dev: `740df89`. 새 작업 기준: `cfb7245`. 최신 누적 PR #51: `f906eef`. PR #15: `29c0404`.
- 별도 `codex/dev-pr-integration-20261118`에서 원래 커밋과 분기 이력을 보존했다. 기존 작업 브랜치의 force push나 재작성은 하지 않는다.
- `0841303`: dev와 최신 PR stack의 25개 충돌 경로를 통합. `4de683a`: #15의 HTTP 인수·음성 보호를 통합하고 검증 환경/화면 회귀를 수정.
- 기존 개별 workitem PR을 유지하고, 이 통합 PR은 분기 간 충돌 해결과 통합 검증을 담당한다. merge commit을 사용하여 원래 PR head를 dev의 조상으로 보존한다.

## 자체 리뷰와 수정

- 음성: dev의 후행 호출부호·숫자 규칙·BERT 경로를 보존하고 파일 업로드 역할 근거를 함께 유지한다. #15의 서버 ATC/PILOT 입력 시 근거 음성 중단 코드는 미반영 상태였으므로 가져왔다. 제거된 모의 입력 UI는 되살리지 않았다.
- 화면: 기존 `/pilot`과 영어/복창 일치 표시를 유지하고 `/cockpit`, `/report`, 새 브랜드·로고·다크 모드·결과 배치를 결합했다. 자동 병합으로 삭제된 scenario UI만 남아 `scenario is not defined`가 발생한 것을 브라우저 테스트에서 발견하여 제거했다.
- 터치: dev의 복수 포인터/취소 보호를 기존 3D 화면에 보존하고 새 Vision 3D 화면에도 적용했다. 회전·핀치 뒤 숫자 편집이 발생하지 않고 다음 정상 클릭으로 HDG0을 입력하는 브라우저 회귀를 보완했다.
- Vision: 현재 프레임 ROI만 판독, 놓침/큰 이동/만료 뒤 3회 안정화 초기화, null/HDG0 구분, 입력 지시 revision, 중복 프레임 차단을 검토했다. 모델·원본 영상·DB는 추가하지 않는다. 모의 화면의 명시적 수집용 display 모드는 기존 실험 기능이며 AI 관측값으로 설정을 바꾸는 경로가 아니다.
- Report: polling과 독립된 서버 평가, 종료 재요청의 동결 자료 유지, 원본 JSON 보존, 사건별 요약 및 미해결/대체 구분, 소유권 확인을 검토했다.
- 환경: 새 CNN fixture가 torch를 직접 import하지만 bootstrap의 test 의존성에 누락돼 있었으므로 Vision test extra에 `torch>=2.8,<3`를 추가했다. 기본 Playwright 실행에도 모의 카메라 플래그를 추가해 전용 report 설정 없이 CI에서 실행되게 했다.
- 문서: 양쪽 작업/검증 기록을 보존했다. 서로 다른 작업에 사용됐던 SPEC-006-WI-05 번호는 원래 Pilot 기록과 별도 Operation 기록을 한 파일에 구분하여 보존한다.
- 원격 #15, #36–#51의 inline review thread는 조회 시 모두 0개였다. 이는 외부 승인이나 자동 리뷰 완료를 뜻하지 않는다.

## 실행 검증

별도 worktree, 임시 DB·합성 입력으로 검증했다. 로컬 Python3.14, Node24.22.3, 설치된 Chromium을 사용했다. Python3.13 고정 의존성/Ubuntu는 원격 CI에서 별도 확인한다.

| 위치·명령 | 실제 결과 |
| --- | --- |
| 루트: `RADAR_INTERFACE_ACCEPTANCE_DIR=<새 임시 경로> .venv/bin/python scripts/verify.py --component backend --component vision --http-smoke` | Backend+실제 HTTP 754 passed / 7 skipped; legacy/v2 HTTP smoke PASS; Vision 80 passed |
| frontend: `npm test` | 83 passed |
| frontend: `npm run build` | PASS; 기존 Three.js 번들 크기 안내 유지 |
| frontend: `RADAR_INTERFACE_ACCEPTANCE_DIR=<위 경로> npm run test:acceptance` | 현재 실행에서 생성한 HTTP bundle 3개를 React로 검증, 5 passed |
| 루트: `.venv/bin/python contracts/check_v2.py` | Schema6 / fixture22 PASS |
| frontend: `RADAR_TEST_PYTHON=../.venv/bin/python RADAR_CHROMIUM_PATH=<설치 경로> npm run test:e2e` | 14 passed: 운영 정상/오류/수정/끊김/복구/종료·PDF, ROI·추적, Pilot5, 3D2, 테마2, 마이크 모의1 |
| 같은 설정에서 `npm run test:e2e -- e2e/cockpit-proportions.spec.js` | 추가한 Vision 복수 포인터 회귀 1 passed |
| `git diff --check` | PASS |

초기 실패는 의존성(Pillow/three/torch), sandbox의 로컬 소켓 차단, 설치된 Chromium과 Playwright 기본 revision 차이, 병합 과정의 scenario 잔여 코드였다. 별도 의존성 설치·허용된 서버 실행·명시적 Chromium·잔여 UI 제거 뒤 위 검증이 통과했다. 테스트 기대 판정이나 안전 기준은 완화하지 않았다. 다크 모드 활성 화면 캡처의 로고·배치·보류 표시를 직접 확인했다.

## 남은 범위와 인수인계

실제 새 마이크/STT 모델·카메라/YOLO/CNN 가중치·태블릿·프린터·OS 앱 설치는 미실행이다. 7 skipped를 성공으로 계산하지 않는다. 기존 실제 촬영 수치는 재검증한 것으로 주장하지 않는다. 최종 실장비 AC가 남은 workitem은 코드 병합만으로 done 처리하지 않는다.

원격 CI와 최종 병합 SHA는 통합 PR에서 확인한다. 모든 원본 PR head의 조상 관계 및 원격/로컬 dev 일치를 병합 후 확인한다. 사용자 DB·모델과 기존 실행 서버는 변경하지 않는다.
