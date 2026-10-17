# 운영 확장 API

기존 legacy API와 radar-observation/1 JSON 구조는 유지한다. 실행 서버의 OpenAPI가 요청 DTO의 원본이다. 소프트웨어 사용은 [운영 안내](../docs/development/operations.md)를 따른다.

| 경로 | 의미 |
| --- | --- |
| GET /api/v1/flights | 기존 비행 목록 |
| GET /api/v1/flights/{flight_id}/clearances | 공통 계약 지시의 현재 단계별 서버 판정 |
| POST /api/v1/flights/{flight_id}/refresh | 활성 지시 freshness 재평가; 변경된 판정만 Trace 기록 |
| POST /api/v1/flights/{flight_id}/input-activity | channel_id, active, lease_seconds(1–60)로 마이크 사용 lease 기록 |
| POST /api/v1/flights/{flight_id}/advisory-policy | actor, voice_enabled, critical_phase, radio_active 명시 |
| POST /api/v1/incidents/{incident_id}/actions | actor/reason + ACKNOWLEDGED/VOICE_REQUESTED/VOICE_PLAYED/VOICE_SUPPRESSED |
| POST /api/v1/clearances/{id}/evidence | PNG/JPEG/PCM WAV raw body 업로드 |
| GET/DELETE /api/v1/clearances/{id}/evidence/{evidence_id} | 지시별 근거 조회/내용 삭제; 다른 지시404·삭제410 |
| GET /api/v1/flights/{id}/report | radar-report/1: summary/classification/timeline/corrections/incidents/advisories/observations/clearances/training_feedback |
| GET /api/v1/flights/{id}/report.json | 동일 리포트 JSON 다운로드 |

수신 관측·판정·사건·Trace는 같은 트랜잭션이다. 사건은 READBACK/COCKPIT 단계별로 OPEN→RESOLVED이며 불확실 입력으로 닫지 않는다. 지시 변경은 SUPERSEDED이고 resolved_at을 만들지 않는다. 검증 단계의 해결과 전체 NORMAL은 별개다. 정상/보류/불일치는 최종 지시별 수, 사건/해결/미해결은 사건 수, 채널 장애/거부 입력은 이벤트 수다. 지연은 UTC 시각 차이이며 모의 환경 측정이다.

동일 사건의 ACK/음성 요청/시작은 한 번만 기록하며 억제는 사유별 한 번이다. 재생 요청을 실제 재생으로 세지 않는다. 브라우저 onstart로 VOICE_PLAYED를 별도 전송한다. 서버는 기본 음성 불허·중요 단계 억제·교신 억제 및 현재 신선한 MISMATCH를 확인한다. 사용자가 전달하는 정책과 실제 장치 상태의 일치는 운영자가 확인해야 한다.

END는 마지막 라이브 판정을 종료 트랜잭션에 고정한다. terminal 리포트의 NORMAL은 종료 시점 결과이며 진행 중 유효성 배지가 아니다. 이후 근거 삭제는 원본 당시 기록을 수정하지 않고 410/삭제 Trace로 구분한다. 종료 시 고정된 리포트에는 종료 후 생성된 삭제 이벤트가 포함되지 않으며 근거 URL 응답이 현재 접근 상태의 원본이다. 자동 보존 기간 삭제 및 사용자 인증은 제공하지 않는 로컬 실험 범위다.
