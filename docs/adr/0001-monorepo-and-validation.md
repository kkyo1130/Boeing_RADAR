# ADR-0001: 모노레포와 중앙 판정

- 날짜: 2026-10-10
- 상태: accepted (디렉터리 분리·기존 backend 이동은 사용자 요청으로 완료)

## 결정

frontend, backend, vision, communication, contracts를 하나의 저장소에서 관리한다. 기존 Python 앱·테스트·requirements를 backend 아래에 보존한다. 현재 FastAPI·SQLAlchemy·SQLite 구현을 유지하고 프론트는 계획상 React다.

Vision/통신은 관측값·품질·근거를 전달하고 Backend가 지시 연결·최종 비교·보류·재검증·저장을 소유한다. 이 책임 경계는 계획 기준이며 실제 입력 어댑터는 아직 미구현이다.

## 이유와 영향

파트별 개발을 분리하면서 계약과 통합 검증을 함께 관리한다. Vision의 OCR 모델, STT 제공자, 전송 방식, 호환성 정책은 SPEC-002/003/004에서 결정한다. 현재 backend 실행은 backend 디렉터리에서 수행한다.

## 채택하지 않은 것

참고 저장소의 Next/Nest/Prisma·Turborepo, develop 브랜치, 강제 squash/직렬 실행을 가져오지 않는다. RADAR의 현재 Python 구현과 기존 dev 브랜치를 따른다.
