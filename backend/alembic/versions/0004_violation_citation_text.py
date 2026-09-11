"""alter violation citation to text

Revision ID: 0004_violation_citation_text
Revises: 0003_rule_configs
Create Date: 2026-09-11 17:38:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_violation_citation_text"
down_revision: str | None = "0003_rule_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "violations",
        "citation",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "violations",
        "citation",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
