"""Start a real loopback HTTP server against a disposable DB and verify legacy flows."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/bin/python")
    args = parser.parse_args()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with TemporaryDirectory(prefix="radar-http-smoke-") as directory:
        env = dict(os.environ, RADAR_DATABASE_URL=f"sqlite:///{Path(directory) / 'smoke.db'}")
        with open(Path(directory) / "server.log", "w+") as log:
            process = subprocess.Popen([str(args.python.absolute()), "-m", "uvicorn", "app.main:app",
                                        "--host", "127.0.0.1", "--port", str(port)],
                                       cwd=ROOT / "backend", env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 15
                while True:
                    try:
                        with urllib.request.urlopen(base + "/openapi.json", timeout=1) as response:
                            assert response.status == 200
                        break
                    except (urllib.error.URLError, TimeoutError):
                        if process.poll() is not None or time.monotonic() > deadline:
                            log.seek(0)
                            raise RuntimeError("Server did not start: " + log.read())
                        time.sleep(0.05)

                def request(path, body=None, method="POST"):
                    data = json.dumps(body).encode() if body is not None else None
                    req = urllib.request.Request(base + path, data=data, method=method,
                                                 headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return json.load(response)

                good = {"altitude": 18000, "heading": 240, "confidence": 0.96}
                bad = {**good, "altitude": 16000}
                flight = request("/api/flights/start")["flight_id"]
                def clearance():
                    return request(f"/api/flights/{flight}/clearances", good)["clearance_id"]
                c = clearance()
                request(f"/api/clearances/{c}/readback", good)
                assert request(f"/api/clearances/{c}/cockpit", good)["status"] == "VERIFIED"
                c = clearance()
                assert request(f"/api/clearances/{c}/readback", bad)["status"] == "READBACK_ERROR"
                assert request(f"/api/clearances/{c}/readback/reverify", good)["status"] == "RESOLVED"
                c = clearance()
                request(f"/api/clearances/{c}/readback", good)
                assert request(f"/api/clearances/{c}/cockpit", bad)["status"] == "SETTING_ERROR"
                assert request(f"/api/clearances/{c}/cockpit/reverify", good)["status"] == "RESOLVED"
                assert request(f"/api/flights/{flight}/end")["status"] == "ENDED"
                events = request(f"/api/flights/{flight}/safety-trace", method="GET")
                assert events[-1]["event_type"] == "FLIGHT_ENDED"
                assert {"VERIFIED", "READBACK_ERROR", "SETTING_ERROR", "RESOLVED"}.issubset(
                    {event["event_type"] for event in events})
                print("PASS: isolated real HTTP, normal/two errors/corrections/end/Trace; no device input.")
                from demo import run
                reports = run(base)
                assert len(reports) == 4
                print("PASS: v1 real HTTP synthetic rehearsal, incidents/uncertainty/corrections/frozen report/export.")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
