# 고정 평가와 버전 비교

`synthetic-labels.json`은 정상/오류 × clean/가림/흐림/잡음/지연/끊김의 **12개 합성 시나리오 프로토콜**이다. 실제 음성·영상 표본이 아니며 현재 모델의 성능 수치로 보고하지 않는다. 라벨은 추론 입력에 제공하지 않는다. 실제 데이터를 추가할 때 허용된 출처, 원본 참조, 정답 작성자, 모델/도구 버전, 조건과 시간 기준을 기록하고 tuning/evaluation ID를 분리한다.

예측 파일은 sample ID마다 정확히 한 항목을 갖는 JSON 배열이다. 각 항목은 `sample_id`, `verdict`(NORMAL/MISMATCH/UNVERIFIED), 선택 `latency_ms`, `fields`, `transcript`를 갖는다. 라벨의 fields/transcript가 있을 때만 해당 파트 exact match를 채점한다. STT 정확 일치는 WER가 아니며 문장 의미 정확도로 해석하지 않는다. 각 파트는 별도 라벨/예측 파일로 평가한다.

```sh
python3 scripts/evaluate.py --dataset contracts/evaluation/synthetic-labels.json --predictions /tmp/predictions-v1.json --model-version local-whisper-v1 --output /tmp/evaluation-v1.json
python3 scripts/evaluate.py --compare /tmp/evaluation-v1.json /tmp/evaluation-v2.json --output /tmp/trend.json
```

동일 데이터 hash의 서로 다른 버전만 비교하며 자동 학습/배포는 수행하지 않는다. 누락/중복 예측, 잘못된 verdict, 음수/무한 지연, 라벨의 training/tuning ID 중복은 실패한다. ID 외의 동일 원본·근접 프레임 유출은 사람이 원본 세션 단위로 확인해야 한다.

지표는 SPEC-009의 2×3 confusion과 탐지·거짓 정상·오탐·경보 정확도·전체/오류 보류를 분자/분모와 함께 보고한다. 분모 0은 null/N/A다. 지연은 측정된 표본 수·평균·최근접 순위 p95·최대값이다. 프레임→관측 또는 오류 발생→화면 표시 중 어떤 지연인지 데이터셋에 기록하며 다른 시간 기준을 섞지 않는다. 측정이 없는 표본을 0ms로 넣지 않는다.

0건의 관측 실패를 위험 0으로 표현하지 않는다. 모델 점수는 보정된 확률이나 검증 정확도가 아니다. 목표 임계값과 실제 인수 세트 규모는 미확정이며, 합성 테스트 통과만으로 SPEC-009의 실장비 인수를 완료하지 않는다.

10/27 중간 점검: 네 시나리오의 실제 입력→근거→UI/음성·억제→fault/복구를 발표 장비에서 기록한다. 11/16 최종: 수정 새 입력→해결→종료 리포트→새 비행 재현, 입력 끊김/미해결/근거 삭제/서버 재연결을 반복한다. 각 실행의 입력 종류(실카메라/마이크/과거 녹음/합성), 명령, 모델·정답 버전, 기대/관찰, 실패와 녹화 참조를 기록한다. 실행 전인 날짜의 시연을 통과로 쓰지 않는다.
