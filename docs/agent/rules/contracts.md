---
paths:
  - "contracts/**"
---

# contracts 개발 규칙

공유 계약은 SPEC-002에서 합의 후 코드화한다. 스키마 버전·단위·UTC 시각·ID·결측·품질·근거·에러를 명시한다.
backend 구현/OpenAPI와 문서 계획을 구분한다. 필드 변경 시 producer와 consumer의 호환성과 fixture를 함께 갱신한다.
부정확하거나 stale한 Observation을 정상 데이터로 바꾸지 않는다. 계약 fixture는 정상·미인식·장애·부분 지시·재검증을 포함한다.
