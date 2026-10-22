"""Bounded local evidence uploads, owned by v2 flight. No URL fetching."""
from io import BytesIO
import wave
import warnings
from uuid import uuid4
from PIL import Image
from app.models.operations_v2 import V2Media
from app.services import receiving_v2 as intake

MAX_BYTES = 20 * 1024 * 1024


def validate(data, mime):
    if not data or len(data) > MAX_BYTES:
        raise intake.ReceivingError(413, 'INVALID_PAYLOAD', 'Evidence must be 1..20 MiB')
    try:
        if mime == 'audio/wav':
            with wave.open(BytesIO(data)) as stream:
                if stream.getcomptype() != 'NONE' or stream.getsampwidth() != 2 or stream.getnchannels() not in (1, 2) or not 8000 <= stream.getframerate() <= 96000:
                    raise ValueError('Use 16-bit PCM WAV')
                frames = stream.getnframes()
                if not frames or frames / stream.getframerate() > 600:
                    raise ValueError('Audio duration must be 0..600 seconds')
                if len(stream.readframes(frames)) != frames * stream.getnchannels() * stream.getsampwidth():
                    raise ValueError('Truncated WAV')
        elif mime in ('image/png', 'image/jpeg'):
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    if image.format != ('PNG' if mime == 'image/png' else 'JPEG'):
                        raise ValueError('Media type differs from bytes')
                    image.verify()
        else:
            raise intake.ReceivingError(415, 'INVALID_PAYLOAD', 'Use PNG, JPEG or PCM WAV')
    except intake.ReceivingError:
        raise
    except (ValueError, OSError, EOFError, wave.Error, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise intake.ReceivingError(422, 'INVALID_PAYLOAD', 'Invalid evidence bytes') from exc


def upload(db, flight_id, data, mime):
    validate(data, mime)
    now = intake.utc_now()
    with intake.atomic(db):
        _, profile = intake.context(db, flight_id, active=True, lock=True)
        token = 'media-' + uuid4().hex
        db.add(V2Media(evidence_id=token, flight_id=flight_id, media_type=mime,
                      content=data, created_at=intake.stamp(now), deleted_at=None))
        profile.revision += 1
        intake.trace(db, profile, 'EVIDENCE_STORED', {'evidence_id': token, 'media_type': mime}, now)
    return dict(evidence_id=token, ref='stored:'+token)


def lookup(db, flight_id, ref):
    item = db.get(V2Media, ref.removeprefix('stored:'))
    if not ref.startswith('stored:') or item is None or item.flight_id != flight_id:
        raise intake.ReceivingError(404, 'NOT_FOUND', 'Evidence not found in this flight')
    if item.deleted_at is not None:
        raise intake.ReceivingError(410, 'NOT_FOUND', 'Evidence was deleted')
    return item


def delete(db, flight_id, evidence_id):
    now = intake.utc_now()
    with intake.atomic(db):
        _, profile = intake.context(db, flight_id, lock=True)
        item = lookup(db, flight_id, 'stored:'+evidence_id)
        item.deleted_at, item.content = intake.stamp(now), None
        profile.revision += 1
        intake.trace(db, profile, 'EVIDENCE_DELETED', {'evidence_id': evidence_id}, now)
    return dict(evidence_id=evidence_id, availability='unavailable')
