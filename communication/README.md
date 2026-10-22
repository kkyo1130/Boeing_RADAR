# 로컬 Whisper 음성 입력

사용자 선택: ATC 녹음 WAV + Pilot 마이크. `radar_audio/audio.py`는 PCM 전처리·고정 구간·silence/약신호/클리핑·마이크 파일 입력을 담당하고, `backend/app/services/speech/local.py`는 로컬 faster-whisper를 담당합니다. `scripts/produce_observation.py`는 기존 v2 구조화 함수를 재사용해 같은 수신 API로 보냅니다.

[설치·실행·한계·검증](../docs/development/operations.md)을 따릅니다. 실제 마이크·정답 교신·자동 화자/중첩/경고 재유입 탐지 검증은 남아 있으며 SDR 코드는 제공하지 않습니다. 원본 WAV와 모델은 Git에 넣지 않습니다.
