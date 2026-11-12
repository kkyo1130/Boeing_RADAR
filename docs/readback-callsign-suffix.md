# Pilot 복창의 뒤쪽 호출부호 지원

기준 dev `0e80cb4`, 작업 `codex/readback-callsign-suffix`, SPEC-004-WI-02 추가 수정.

제출: 구현 `7416738`, [PR #34](https://github.com/kkyo1130/Boeing_RADAR/pull/34). 로컬 8018 데모에는 기존 Pilot 표시 PR #33과 함께 별도 `codex/demo-readback-preview` 브랜치로 적용했다. 기존 비행·원음은 유지하며 이 작업에서 PR을 병합하지 않았다.

## 문제와 변경

실제 사용자 DELTA123 녹음의 전사는 `3,000 feet heading, two, seven, zero, delta, one, two, three.`였다. 기존 adapter/구조 검사는 호출부호 접두어만 허용했고 BERT도 뒤쪽 호출부호를 놓쳐 복창을 해석하지 못했다.

- PILOT 역할에 한해 등록된 호출부호가 문장 처음 또는 끝에 정확히 한 번 나타나는지 확인한다. 중간 호출부호, 복수/중복/겹친 alias, 미등록·부분 호출부호는 보류한다. target 값에서 호출부호를 채우거나 STT를 보정하지 않는다. ATC는 기존 문법을 유지한다.
- `climb/climbing`, `descend/descending`, `maintain/maintaining`, `to`, `altitude`, `fly/flying heading`, `turn/turning left/right heading` 복창 문형을 지원한다. 전체 문장을 소비하고 조건·부정·정정·중복 숫자·잘린 문장을 임의 삭제하지 않는다.
- BERT+규칙 결과에 호출부호가 **없을 때만** 실제 발화에 포함된 등록 alias를 결정론적 후보로 추가한다. 고도도 명시 단위가 있는 지원 복창에만 보완한다. 출처 `registered_readback_rule`, 점수 null, 원문 문자 위치와 `base_entities/base_issues`, 원시 tokens를 보존한다. 후보 entity와 원래 tokens는 보완 전후 자료이므로 동일 BIO 결과라고 해석하지 않는다.
- BERT의 다른 호출부호 예측, 잘못된 BIO, 모델 실패, 조건 관련 보류를 무시하지 않는다. 모델이 설정됐는데 실패하면 규칙만으로 승인하지 않는다. 실제 관제/파일럿 모델 재학습은 하지 않았다.
- 숫자만 있는 고도 복창은 후보를 보존하되 `READBACK_ALTITUDE_ACTION_MISSING`으로 보류한다. 채택한 ATC의 상승·하강/회전 방향을 지시 ID별로 저장해 복창에서 빠지거나 반대이면 보류한다. 숫자 불일치와 동작 확인 불가를 구분한다. 이전 DB 지시에 이 정보가 없으면 새 지시를 요구한다.
- 운영 화면의 호출부호 안내에서 고정된 Radar 문구를 제거하고 새 보류 사유를 한국어로 표시한다. 전체 ICAO/FAA 문구 준수 검사나 운항 안전 인증 기능은 아니다.

## 지침 근거와 구현 범위

[FAA AIM 4-4-7](https://www.faa.gov/Air_traffic/Publications/atpubs/aim_html/chap4_section_4.html)은 호출부호 포함과 지시 순서에 따른 고도·벡터 복창을 안내하며 뒤쪽 호출부호 예시를 제공한다. [CAA CAP413 §2.69 및 §3.10](https://www.caa.co.uk/media/km2juvmx/cap413-edition-24-radio-telephony.pdf)은 복창 항목 및 상승·하강 예시를 제공한다. 국가·상황별 표현 차이를 모두 구현했다는 의미가 아니다. 동작 생략 보류는 이 프로토타입의 보수적 지원 범위이며 모든 실제 숫자 중심 리드백이 규정 위반이라는 판정이 아니다.

## 실제 원음 재시험

원본 live-demo DB는 읽기 전용으로 열고 마지막 성공 ATC와 PILOT의 WAV를 그대로 추출했다. 별도 시험 DB/비행에서 실제 faster-whisper base.en → 실제 BERT → 보완 규칙 → 등록/수신/구조 검사를 HTTP로 실행했다. 새 마이크 녹음이나 스피커-마이크 재수음은 아니다. 원래 녹음 시각은 manifest, 시험 주입 시각은 새 segment에 분리 기록했다. 정답 호출부호/숫자를 STT 힌트로 주입하지 않았다.

| 항목 | 수정 전 | 수정 후 |
| --- | --- | --- |
| 원본 ATC | DELTA123 / 3000ft / 270°, PASS | 같은 전사·값, PASS |
| 원본 Pilot 호출부호 | 추출 실패 | DELTA123, 등록 호출부호 검사 PASS |
| 원본 Pilot 고도·방위 | adapter fields 비어 있음 | 후보 3000ft / 270°, 원문과 숫자 검사 PASS |
| 원본 Pilot 최종 판정 | UNVERIFIED | UNVERIFIED: 상승·하강·유지 표현 생략 및 ATC 상승 방향 미확인 |
| Cockpit 설정 | 카메라 없음 | 계속 UNVERIFIED |

원음 SHA-256:
- ATC: `0f62d3d90e5b9eb70f8a6606033faab3bb22fadbbddf777b7c9b222301a2d579`
- Pilot: `fd51f22ee339840f6f04e3884f70c360aa3267854ee2a5d38d8b608a15ebf8cf`

전사는 수정 전과 두 파일 모두 동일했다. raw audio/DB/전체응답은 Git-ignored `.demo/delta-readback-replay/`에 보존한다. 별도의 텍스트 시험에서 `Climb and maintain three thousand feet, heading two seven zero, Delta one two three.` 및 `Climbing to ...`는 실제 BERT+후처리 후보 검사를 통과했다. 이것을 새 음성 시험 성공으로 계산하지 않는다.

## 검증/재현

- backend 전체: `RADAR_TEST_BERT_MODEL=<prepared-bert> OMP_NUM_THREADS=4 ../.venv/bin/python -m pytest -q` — 665 passed, 1 skipped(v7 별도 가중치 미지정). 추가 경계/실제 BERT 텍스트 사례를 더한 전용 `test_readback_phraseology.py` 최종 42 passed.
- 기존 숫자 불일치/incident 테스트 8건은 상승 지시에 대한 복창 fixture에도 상승 표현을 포함하도록 수정했다. 원래 숫자 불일치·보류·복구 기대값은 유지했고 동작 누락/반대 보류를 별도로 추가했다.
- `contracts/check_v2.py`: 6 schemas / 22 fixture expectations PASS. 공개 DTO/Schema 변경 없음.
- frontend build 성공. 기존 큰 번들 경고가 남음. UI 문구만 수정했으며 새 브라우저 마이크 시험은 미실행.
- 최초 루트 pytest는 import 경로 때문에, 최초 replay는 UTC 형식/ATC 종료보다 앞선 가상 캡처 시각 때문에 실패했다. 실제 제품 검사를 약화하지 않고 실행 위치 및 replay 주입 시각을 고친 후 성공했다.

재현: `python scripts/replay-readback.py --server http://127.0.0.1:<port> --callsign DELTA123 --atc <original-atc.wav> --readback <original-pilot.wav> --output <local-output>`.

## 자체 리뷰와 남은 범위

원문/모델 결과 보존, 잘못된 호출부호 강제 교정 금지, 동작 누락의 거짓 정상 방지, fresh segment/지시 연결, 카메라 부재 보류 및 실제 음원/fixture 구분을 확인했다. 독립적인 두 안전 채널이나 새 데이터 정확도 평가로 주장하지 않는다. 속도·조건부 지시·제약·정정·전체 phraseology 검증은 지원하지 않으며 입력 보류를 유지한다. PR 외부 리뷰 및 병합은 별도다.

## PR #34 CI 실패 후속 수정

`3621435`의 원격 run `43002860489`에서 Linux/macOS 모두 HTTP 통합 fixture 4건이 실패했다. 숫자 불일치를 시험하는 입력이 상승 지시에 대해 `maintain`만 복창해 새 동작 검사에 보류됐기 때문이다. 숫자 오류·incident·복구 기대값은 유지하고 해당 fixture에 `climb and maintain`을 명시했다. 상승 표현 누락 및 반대 방향이 계속 UNVERIFIED인지, 뒤쪽 호출부호가 있는 정상 복창은 NORMAL인지 HTTP 회귀 3건을 추가했다.

프런트는 호출부호 안내를 바꾼 뒤 옛 문구를 검사하던 단위 테스트 1건이 실패했다. 현재 비행 호출부호 안내가 나오고 Radar가 고정되지 않는지 검사하도록 수정했다. 제품 판정 로직과 보류 기준은 변경하지 않았다.

처음 로컬 검증에서 `backend/tests`만 실행하고 별도 `tests/integration` 및 프런트 단위 테스트를 누락한 범위 차이를 확인했다. CI와 같은 `scripts/verify.py --component backend --component vision --component frontend --http-smoke`로 재검증: backend/HTTP 713 passed, 6 skipped(모델 opt-in), Vision45, frontend60, build 및 legacy/v2 HTTP smoke 통과. 브라우저 첫 실행은 로컬 기본 Chromium 실행 파일 부재로 시작하지 못했으며 설치된 Chromium 경로를 지정해 재실행한다. 새 녹음이나 모델 추론 재검증은 이번 테스트 수정 범위에 포함하지 않는다.

Local Chromium fixture E2E: `RADAR_CHROMIUM_PATH=<installed-headless-shell> npm run test:e2e` — 9 passed (42.6s).
