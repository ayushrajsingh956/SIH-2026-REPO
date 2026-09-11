"""add rule_configs table for admin dynamic rule toggles and severity overrides

Revision ID: 0003_rule_configs
Revises: 0002_auth_refresh_tokens
Create Date: 2026-09-11 17:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_rule_configs"
down_revision: str | None = "0002_auth_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_configs",
        sa.Column("code", sa.String(length=100), primary_key=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("severity_override", sa.String(length=50), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_rule_configs_is_enabled"), "rule_configs", ["is_enabled"], unique=False
    )


def downgrade() -> None:
    op.drop_table("rule_configs")
