---
paths:
  - "backend/**"
---

# backend 개발 규칙

중심 서버가 지시 연결·최종 판정·경고 정책·저장을 소유한다. Vision/통신에 판정 로직을 중복하지 않는다.
현재 `app.services`의 서비스 모듈은 작동 중이다. 빈 확장 폴더가 있다는 이유로 기존 모듈을 불필요하게 쪼개지 않는다.
현재 Observation은 ALT·HDG·confidence 필수다. null·quality·evidence를 지원한다고 가정하지 말고 SPEC-002에서 호환성·DB 변경을 구현한다.
백엔드 실행과 테스트는 backend 디렉터리에서 수행한다: `python -m pytest -q`, `uvicorn app.main:app --reload`. 가상환경이 준비된 경우 `.venv/bin/python -m pytest -q`를 사용한다. 루트에서 그대로 실행하면 app import가 실패할 수 있다.
데이터 변경과 Safety Trace는 같은 트랜잭션으로 저장한다. 오류 수정 해결과 전체 3단계 검증 완료는 구분한다.
