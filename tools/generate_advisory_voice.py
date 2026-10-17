"""Rebuild fixed Korean prototype prompts on macOS (Yuna); no user recordings."""
from pathlib import Path
import subprocess
import tempfile

PHRASES = {'alt':'고도 설정을 확인하세요', 'hdg':'방위 설정을 확인하세요',
    'both':'고도와 방위 설정을 확인하세요', 'readback':'복명복창 내용을 확인하세요',
    'visibility':'계기판이 보이도록 해주세요', 'camera':'카메라 연결을 확인하세요'}
root = Path(__file__).resolve().parents[1]/'frontend/public/voice'
root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='radar-prompts-') as directory:
    for name, text in PHRASES.items():
        source = str(Path(directory)/(name+'.aiff'))
        subprocess.run(['/usr/bin/say', '-v', 'Yuna', '-r', '185', '-o', source, text], check=True)
        subprocess.run(['/usr/bin/afconvert', '-f', 'WAVE', '-d', 'LEI16', source, str(root/(name+'.wav'))], check=True)
