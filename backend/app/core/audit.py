import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record_audit_event(
    db: AsyncSession,
    action: str,
    entity_type: str,
    user_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    """Inserts a structured audit log entry."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    )
    db.add(entry)
    await db.flush()
    return entry
