# RADAR 개발 스펙 진입점

현재 어디까지 구현됐는지는 [구현 현황](docs/IMPLEMENTATION_STATUS.md)에서 확인합니다.

기획과 자문을 반영한 기능별 스펙과 workitem의 원본은 `docs/spec/`입니다.

- [전체 스펙](docs/spec/README.md): 10개 기능 스펙.
- [전체 작업 목록](docs/spec/todo.md): 담당 제안·의존성·현재 상태.
- [세현님 Vision 작업](docs/spec/003-cockpit-vision.md): 촬영/ROI → 카메라 상태 → 숫자/품질 → 근거/전송 → 실장비 검증.
- [공통 데이터 계약](docs/spec/002-observation-contracts.md): 파트 연결 전에 합의할 내용.
- [현재 구현과 결정 필요 사항](docs/service/overview.md).
- [원본 기능 대응](docs/service/requirements-map.md).

스펙은 목표 초안입니다. 기존 서버 Mock 기능을 실제 음성/카메라 연동 완료로 해석하지 않습니다. 사용자에게 명확히 요청받은 WI만 구현하고 미정 사항은 영향을 받는 작업에 연결합니다.
