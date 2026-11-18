# 2026-11-17 게시 기록

사용자 명시 요청 ‘푸시 및 pr’에 따라 검증된 10개 작업 브랜치를 force 없이 origin에 게시하고 작업별 Draft PR을 생성했다. 기존 PR #39 뒤에 아래 순서로 연결했다. 병합·자동 병합·기존 사용자 체크아웃 교체는 수행하지 않았다.

| PR | 작업 | head | base |
| --- | --- | --- | --- |
| [#40](https://github.com/kkyo1130/Boeing_RADAR/pull/40) | [SPEC-009-WI-08] Cockpit HDG·ALT 비율 조정 | `codex/cockpit-proportions-20261116` | `codex/report-events-print-20261116` |
| [#41](https://github.com/kkyo1130/Boeing_RADAR/pull/41) | [SPEC-003-WI-09] 이동 중 인식 영역 갱신과 연속 재탐색 | `codex/camera-motion-tracking-20261116` | `codex/cockpit-proportions-20261116` |
| [#42](https://github.com/kkyo1130/Boeing_RADAR/pull/42) | [SPEC-008-WI-07] 반복 관측·사건 갱신의 리포트 중복 표시 제거 | `codex/report-dedup-20261116` | `codex/camera-motion-tracking-20261116` |
| [#43](https://github.com/kkyo1130/Boeing_RADAR/pull/43) | [SPEC-003-WI-10] 실제 카메라를 YOLO MCP 검출→CNN OCR로 복구 | `codex/yolo-cnn-webcam-20261117` | `codex/report-dedup-20261116` |
| [#44](https://github.com/kkyo1130/Boeing_RADAR/pull/44) | [SPEC-008-WI-08] Error Timeline을 오류 사건별 네 단계로 요약 | `codex/report-incident-timeline-20261117` | `codex/yolo-cnn-webcam-20261117` |
| [#45](https://github.com/kkyo1130/Boeing_RADAR/pull/45) | [SPEC-008-WI-09] AI Safety Summary 문단 가독성 개선 | `codex/report-summary-layout-20261117` | `codex/report-incident-timeline-20261117` |
| [#46](https://github.com/kkyo1130/Boeing_RADAR/pull/46) | [SPEC-006-WI-06] 중복 음성 입력 선택과 모의 시험 UI 정리 | `codex/operation-input-cleanup-20261117` | `codex/report-summary-layout-20261117` |
| [#47](https://github.com/kkyo1130/Boeing_RADAR/pull/47) | [SPEC-006-WI-07] 복명복창·Cockpit 결과를 하단 독립 두 열로 배치 | `codex/operation-results-layout-20261117` | `codex/operation-input-cleanup-20261117` |
| [#48](https://github.com/kkyo1130/Boeing_RADAR/pull/48) | [SPEC-006-WI-08] Flight Guard 브랜드와 참고 이미지의 밝은 파랑·민트 팔레트 | `codex/flight-guard-blue-theme-20261117` | `codex/operation-results-layout-20261117` |
| [#49](https://github.com/kkyo1130/Boeing_RADAR/pull/49) | [SPEC-006-WI-09] 저장되는 라이트·다크 모드 전환 | `codex/dark-mode-20261117` | `codex/flight-guard-blue-theme-20261117` |

각 PR 본문에 실행한 검증과 미실행 실장비/외부 리뷰를 구분했다. 원본 모델·카메라/음성·DB는 게시하지 않았다. 사용자 작업 폴더의 별도 미커밋 변경과 타 개발자의 브랜드/문구 수정은 포함하지 않고 보존했다. 구현 시점 workitem의 ‘로컬 전용/PR 미제출’ 문구는 게시 이전 기록이며 이 문서와 연결된 PR이 현재 게시 근거다.

최신 UI의 검증은 frontend82·빌드, 다크 모드 브라우저2 통과다. 리포트 변경 backend701/skip7·브라우저4 등 각 작업의 상세 수치는 해당 PR/workitem을 따른다. 새 코드 변경 없이 게시했으며 GitHub CI/외부 리뷰 완료를 주장하지 않는다.


추가 사용자 요청으로 현재 폴더의 실제 누락 문구·검증 기록을 [PR #50](https://github.com/kkyo1130/Boeing_RADAR/pull/50)에 게시했다. 기존 PR에 포함하지 않았던 사용자 브랜드·Cockpit 문구도 이 PR에 반영되며, 현재 checkout은 최신 선행 기준의 `codex/operation-current-labels-20261117`로 정리했다. 원래 전체 작업은 stash 백업에 보존했다.
