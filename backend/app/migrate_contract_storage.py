"""Add contract tables without rewriting legacy data: python -m app.migrate_contract_storage."""
from app.db import engine
from app.models import flight  # Register the existing foreign key target.
from app.models.contract_observation import ContractClearance, ContractEvent


def upgrade(target_engine):
    # Additive and idempotent; no automatic destructive downgrade.
    ContractClearance.__table__.create(target_engine, checkfirst=True)
    ContractEvent.__table__.create(target_engine, checkfirst=True)


if __name__ == "__main__":
    upgrade(engine)
