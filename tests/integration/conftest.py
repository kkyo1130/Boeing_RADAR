from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import main
from app.db import Base, get_db, make_engine
from app.services import contract_service
from mock_contract_producer import MockContractProducer


@pytest.fixture
def producer(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'contract-integration.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    clock = [datetime(2026, 10, 13, tzinfo=timezone.utc)]
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(contract_service, "utc_now", lambda: clock[0])
    monkeypatch.setenv("RADAR_OBSERVATION_MAX_AGE_SECONDS", "30")

    def capture():
        clock[0] += timedelta(seconds=1)
        return clock[0]

    def db_override():
        with sessions() as db:
            yield db

    main.app.dependency_overrides[get_db] = db_override
    try:
        with TestClient(main.app) as client:
            flight = client.post("/api/flights/start").json()["flight_id"]
            clearance = client.post(f"/api/v1/flights/{flight}/clearances").json()["clearance_id"]
            yield MockContractProducer(client, flight, clearance, capture)
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        engine.dispose()
