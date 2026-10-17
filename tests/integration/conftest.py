"""Run the unmodified application in a separate process with a disposable DB."""
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from mock_producer import MockProducer, ROOT


@pytest.fixture(scope="session")
def live_backend(tmp_path_factory, evidence_root):
    directory = tmp_path_factory.mktemp("http-backend")
    env = dict(os.environ, RADAR_EVIDENCE_ROOT=str(evidence_root), RADAR_DATABASE_URL=f"sqlite:///{directory / 'integration.db'}",
        RADAR_V2_CONFIG=str(ROOT / "contracts/examples/integration/config.json"))
    # Bind once, then pass the listening socket to uvicorn: no port allocation race.
    with socket.socket() as listener, (directory / "server.log").open("w+") as log:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
            "--fd", str(listener.fileno()), "--log-level", "warning"],
            cwd=ROOT / "backend", env=env, pass_fds=(listener.fileno(),), stdout=log, stderr=log)
        try:
            deadline = time.monotonic()+15
            with httpx.Client(base_url=base_url, timeout=0.5, trust_env=False) as client:
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        if client.get("/openapi.json").status_code == 200:
                            yield base_url
                            return
                    except httpx.TransportError:
                        pass
                    time.sleep(0.05)
            log.seek(0)
            pytest.fail("Temporary backend did not start: "+log.read())
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture
def producer(live_backend, tmp_path):
    producer = MockProducer(live_backend, tmp_path / "exchange.json")
    try:
        producer.start()
        yield producer
    finally:
        producer.close()


@pytest.fixture(scope='session')
def evidence_root(tmp_path_factory):
    """Disposable media used only by synthetic integration producers."""
    return tmp_path_factory.mktemp('interface-evidence')
