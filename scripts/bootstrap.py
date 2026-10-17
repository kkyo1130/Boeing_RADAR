"""Install implemented parts in one environment; no camera or model download."""
import argparse
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--speech", action="store_true", help="Install optional local Whisper and microphone dependencies")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Python 3.11+ is required; reference environment is Python 3.13")
    environment = args.venv.resolve()
    python = environment / "bin/python"
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    version = subprocess.check_output([str(python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], text=True).strip()
    if tuple(map(int, version.split("."))) < (3, 11):
        parser.error("The selected virtual environment requires Python 3.11+")
    constraints = ["-c", str(ROOT / "requirements-dev-py313.lock")] if version == "3.13" else []
    if not constraints:
        print(f"Python {version}: resolving declared ranges; locked reference is Python 3.13", flush=True)
    subprocess.run([str(python), "-m", "pip", "install", *constraints,
                    "-r", str(ROOT / "backend/requirements.txt"),
                    "-e", str(ROOT / "vision") + "[test,capture]"], cwd=ROOT, check=True)
    if args.speech:
        subprocess.run([str(python), "-m", "pip", "install", *constraints,
                        "-r", str(ROOT / "communication/requirements-local.txt")], cwd=ROOT, check=True)
    if not args.skip_frontend:
        subprocess.run(["npm", "ci", "--cache", str(environment / "npm-cache")], cwd=ROOT / "frontend", check=True)
    print(f"Installed. Verify: {sys.executable} scripts/verify.py --python {python}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"Installation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
