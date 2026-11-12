import hashlib
import re
import secrets
from fastapi import HTTPException
from app.models.operations_v2 import V2ReportOwner

COOKIE='radar_report_owner'

def browser_token(request):
    token=request.cookies.get(COOKIE,'')
    return token if re.fullmatch(r'[0-9a-f]{64}',token) else secrets.token_hex(32)

def digest(token):return hashlib.sha256(token.encode()).hexdigest()

def authorize(db,flight_id,request):
    row=db.get(V2ReportOwner,flight_id)
    token=request.cookies.get(COOKIE,'')
    if not row or not token or not secrets.compare_digest(row.owner_hash,digest(token)):
        raise HTTPException(403,'This browser does not own the flight report')


def main():
    """Local DB administrator only: grant an unowned legacy report."""
    import argparse
    from sqlalchemy.orm import Session
    from app.db import engine
    from app.migrate_observation_v2 import migrate
    from app.models.observation_v2 import V2FlightContext
    parser=argparse.ArgumentParser(description='Issue a local recovery code for an unowned legacy report. Never share codes or use in URLs.')
    parser.add_argument('--flight',required=True)
    args=parser.parse_args();migrate(engine)
    with Session(engine) as db:
        if not db.get(V2FlightContext,args.flight):parser.error('Flight does not exist')
        if db.get(V2ReportOwner,args.flight):parser.error('Flight already has an owner; refusing reassignment')
        token=secrets.token_hex(32)
        db.add(V2ReportOwner(flight_id=args.flight,owner_hash=digest(token)));db.commit()
    print('Private report access code (paste into the report access form; never into a URL):')
    print(token)


if __name__=='__main__':main()
