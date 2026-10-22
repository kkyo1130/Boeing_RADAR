# v2 근거 저장 및 종료 리포트

관측·segment·판정 계약은 기존 [v2 수신 계약](receiving-v2.md)을 유지한다. 이 확장은 별도 판정/사건 엔진을 만들지 않는다.

| API | 요청/결과 |
| --- | --- |
| POST `/api/v2/flights/{flight_id}/media` | raw PNG/JPEG/16-bit PCM WAV, 1..20 MiB. 201: `evidence_id`, `ref: stored:<id>` |
| DELETE `/api/v2/flights/{flight_id}/media/{evidence_id}` | bytes 삭제/Trace. 다른 비행/없는 ID 404, 이미 삭제된 파일 410 |
| GET `/api/v2/flights/{flight_id}/report` | `schema_version: radar-report/2`, snapshot, summary, incidents, observations, timeline |
| GET `/api/v2/flights/{flight_id}/report.json` | 동일 JSON + attachment 헤더 |

업로드 응답에 기존 EvidenceRef의 `kind`, `field`, `roi`를 추가해 `evidence_refs`에 넣는다. 미디어 열람은 기존 [근거 API](evidence-v2.md)의 선택 범위/비행 검사를 거친다. PNG/JPEG는 형식 검증, WAV는 PCM/채널/샘플레이트/길이 검증을 수행한다. 업로드는 활성 비행만 허용한다. 삭제는 종료 후에도 가능하며 과거 판정을 바꾸지 않는다.

리포트는 v2의 현재 판정과 입력/Trace에서 생성한다. 종료 트랜잭션은 마지막 라이브 snapshot을 고정하고 FLIGHT_ENDED까지 저장한다. terminal=true와 함께 snapshot.status=ACTIVE가 올 수 있는데, 이는 종료 직전의 마지막 활성 상태라는 뜻이다. 기존 state endpoint는 종료 뒤 UNVERIFIED를 유지한다. 기존 종료 비행에 frozen report가 없으면 현재의 종료/보류 상태로 보고하며 과거 정상 판정을 추정하지 않는다.

summary normal/mismatch/unverified는 READBACK+SETTING 항목 수, incidents/resolved/open/superseded는 발생 건 수, inputs/not_applied는 수신 입력 수다. 학습된 정확도나 비행 단위 성공률이 아니다. 사용자 확인/음성 결과/수정 근거는 원래 v2 incidents와 timeline에 보존한다.

종료 후 파일 삭제 Trace는 별도로 조회하며 frozen report를 다시 쓰지 않는다. 삭제된 파일 410, 다른 비행 파일 404. DB 기존 v1 테이블은 변경하지 않으며 API에서 자동 변환하지 않는다.
