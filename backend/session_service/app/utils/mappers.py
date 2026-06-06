from app.models.session import Session
from app.schemas.session import SessionRead


def session_to_read(s: Session) -> SessionRead:
    return SessionRead(
        id=s.id,
        host_id=s.host_id,
        title=s.title,
        description=s.description,
        session_type=s.session_type,
        price=s.price,
        max_participants=s.max_participants,
        participant_count=len(s.participants),
        participants=s.participants,
        status=s.status,
        scheduled_time=s.scheduled_time,
        longitude=s.location.coordinates[0],
        latitude=s.location.coordinates[1],
        address=getattr(s, "address", ""),
        subject_tags=s.subject_tags,
        avg_rating=getattr(s, "avg_rating", 0.0),
        total_ratings=getattr(s, "total_ratings", 0),
        created_at=s.created_at,
    )
