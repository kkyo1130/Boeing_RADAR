"""Report existing v2 decisions and traces without a second decision engine."""
from copy import deepcopy
from sqlalchemy import select
from app.models.observation_v2 import V2Input, V2TraceEvent
from app.models.operations_v2 import V2Report
from app.services import receiving_v2 as intake


def report(db, flight_id, *, final_snapshot=None):
    intake.context(db, flight_id)
    frozen = db.get(V2Report, flight_id)
    if frozen:
        return deepcopy(frozen.data)
    state = final_snapshot if final_snapshot is not None else intake.get_state(db, flight_id)
    events = db.scalars(select(V2TraceEvent).where(V2TraceEvent.flight_id == flight_id).order_by(V2TraceEvent.id)).all()
    inputs = db.scalars(select(V2Input).where(V2Input.flight_id == flight_id).order_by(V2Input.id)).all()
    incidents = state['incidents']
    rows = [r for group in ('readback', 'setting') for r in state['validation'][group]['fields']]
    data = dict(schema_version='radar-report/2', flight_id=flight_id, callsign=state['callsign'],
        terminal=final_snapshot is not None or state['status'] == 'ENDED',
        generated_at=intake.stamp(intake.utc_now()), snapshot=deepcopy(state),
        summary={**{key.lower(): sum(r['result'] == key for r in rows) for key in ('NORMAL', 'MISMATCH', 'UNVERIFIED')},
            'incidents': len(incidents), 'resolved': sum(i['status'] == 'RESOLVED' for i in incidents),
            'open': sum(i['status'] == 'OPEN' for i in incidents),
            'superseded': sum(i['status'] == 'SUPERSEDED' for i in incidents),
            'inputs': len(inputs), 'not_applied': sum(not r.applied for r in inputs)},
        incidents=deepcopy(incidents),
        timeline=[dict(sequence=e.id, event_type=e.event_type, occurred_at=e.occurred_at,
                       revision=e.revision, snapshot=e.snapshot) for e in events],
        observations=[dict(input_id=r.input_id, kind=r.kind, applied=r.applied, reason=r.reason,
                           received_at=r.received_at, payload=r.payload) for r in inputs],
        limitations='Field counts are not flight or model accuracy. Terminal snapshot is the last live verdict, not current clearance to operate.')
    if final_snapshot is not None:
        db.add(V2Report(flight_id=flight_id, data=data))
    return data
