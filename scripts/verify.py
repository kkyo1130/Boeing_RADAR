"""Repeatable local/CI checks; isolates the backend from the developer database."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/bin/python")
    parser.add_argument("--component", action="append", choices=["backend", "vision", "frontend"])
    parser.add_argument("--http-smoke", action="store_true", help="Also run isolated real HTTP legacy smoke")
    args = parser.parse_args()
    components = args.component or ["backend", "vision", "frontend"]
    if args.http_smoke and "backend" not in components:
        parser.error("--http-smoke requires the backend component")
    # Preserve the venv executable symlink; resolving it would run system Python.
    python = str(args.python.absolute())
    print("NOT RUN BY THIS SUITE: physical camera/microphone/SDR, native OCR engine, browser E2E, live producer adapters.", flush=True)
    with TemporaryDirectory(prefix="radar-verify-") as folder:
        env = dict(os.environ, RADAR_DATABASE_URL=f"sqlite:///{Path(folder) / 'isolated.db'}")
        for component in components:
            print(f"CHECK: {component}", flush=True)
            if component == "backend":
                subprocess.run([python, "-m", "pytest", "tests", "../tests/integration", "-q"],
                               cwd=ROOT / "backend", env=env, check=True)
                if args.http_smoke:
                    subprocess.run([python, str(ROOT / "scripts/smoke_backend.py"), "--python", python],
                                   cwd=ROOT, env=env, check=True)
            elif component == "vision":
                subprocess.run([python, "-m", "pytest", "vision/tests", "-q"], cwd=ROOT, env=env, check=True)
            else:
                subprocess.run(["npm", "test"], cwd=ROOT / "frontend", check=True)
                subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", check=True)
    print("PASS: all selected automated checks completed.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"FAIL: {error}. Install dependencies with scripts/bootstrap.py first.", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.CalledProcessError as error:
        print(f"FAIL: selected check exited with code {error.returncode}", file=sys.stderr)
        raise SystemExit(1)
