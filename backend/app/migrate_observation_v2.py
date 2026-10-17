"""Idempotent additive migration: python -m app.migrate_observation_v2 --database-url ..."""
import argparse
from sqlalchemy import select
from app.db import Base, make_engine, now
from app.models import flight, clearance, safety_event, observation_v2  # noqa: F401
from app.models.observation_v2 import V2Migration


def migrate(engine):
    # Existing tables are never altered or rebuilt. New v2 tables are additive.
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        if connection.scalar(select(V2Migration.version).where(V2Migration.version == "observation-v2/1")) is None:
            connection.execute(V2Migration.__table__.insert().values(version="observation-v2/1", applied_at=now()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    engine = make_engine(args.database_url)
    try:
        migrate(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
