from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def paginate(
    db: AsyncSession,
    stmt: Select,
    page: int,
    limit: int,
    order_by: Any,
) -> tuple[Sequence[Any], int]:
    """Shared offset pagination: applies count + window to a filtered select.

    Returns (items, total). Callers build their filtered statement, this
    handles the count query, ordering, offset/limit fan-out.
    """
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    items = (
        (await db.execute(stmt.order_by(order_by).offset((page - 1) * limit).limit(limit)))
        .scalars()
        .all()
    )
    return items, total
