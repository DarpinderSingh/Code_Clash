from typing import Optional
from sqlalchemy.orm import Session
from app.models import AuditLog, User
from app.clock import ClockProtocol


def log_action(
    session: Session,
    actor: Optional[User],
    clock: ClockProtocol,
    action: str,
    entity: str,
    entity_id: Optional[int] = None,
) -> AuditLog:
    actor_id = actor.id if actor else None
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        timestamp=clock.now_utc(),
    )
    session.add(entry)
    session.flush()
    return entry
