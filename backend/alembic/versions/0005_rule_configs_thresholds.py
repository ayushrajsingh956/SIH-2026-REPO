"""add thresholds column to rule_configs

Revision ID: 0005_rule_configs_thresholds
Revises: 0004_violation_citation_text
Create Date: 2026-09-11 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_rule_configs_thresholds"
down_revision: str | None = "0004_violation_citation_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rule_configs",
        sa.Column("thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rule_configs", "thresholds")
