"""initial schema with pg_trgm and 7 core tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pg_trgm extension for fuzzy matching
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    # 2. Table: users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="viewer", nullable=False),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 3. Table: products
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("manufacturer_name", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("gtin", sa.String(length=100), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "first_scanned",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_products_barcode"), "products", ["barcode"], unique=True)
    op.create_index(op.f("ix_products_gtin"), "products", ["gtin"], unique=True)
    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    # 4. Table: scans
    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "scanned_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=50), server_default="retail", nullable=False),
        sa.Column("image_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="queued", nullable=False),
        sa.Column("verdict", sa.String(length=50), nullable=True),
        sa.Column("compliance_score", sa.Float(), nullable=True),
        sa.Column(
            "font_check_mode", sa.String(length=50), server_default="relative", nullable=False
        ),
        sa.Column("surface_area_cm2", sa.Float(), nullable=True),
        sa.Column("pipeline_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "scanned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_scans_product_id"), "scans", ["product_id"], unique=False)
    op.create_index(op.f("ix_scans_scanned_by"), "scans", ["scanned_by"], unique=False)
    op.create_index(op.f("ix_scans_status"), "scans", ["status"], unique=False)
    op.create_index(op.f("ix_scans_verdict"), "scans", ["verdict"], unique=False)
    op.create_index(op.f("ix_scans_scanned_at"), "scans", ["scanned_at"], unique=False)
    op.create_index(
        "ix_scans_search_vector",
        "scans",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    # 5. Table: extractions
    op.create_table(
        "extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "model", sa.String(length=100), server_default="gemini-2.5-flash", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_extractions_scan_id"), "extractions", ["scan_id"], unique=True)

    # 6. Table: violations
    op.create_table(
        "violations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_code", sa.String(length=100), nullable=False),
        sa.Column("rule_title", sa.String(length=255), nullable=False),
        sa.Column("citation", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("observed_value", sa.Text(), nullable=True),
        sa.Column("expected_value", sa.Text(), nullable=True),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("overridden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_violations_scan_id"), "violations", ["scan_id"], unique=False)
    op.create_index(op.f("ix_violations_rule_code"), "violations", ["rule_code"], unique=False)
    op.create_index(op.f("ix_violations_severity"), "violations", ["severity"], unique=False)
    op.create_index(op.f("ix_violations_field_name"), "violations", ["field_name"], unique=False)
    op.create_index("ix_violations_scan_rule", "violations", ["scan_id", "rule_code"], unique=False)

    # 7. Table: reports
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pdf_url", sa.String(length=1024), nullable=True),
        sa.Column("docx_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "generated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_reports_scan_id"), "reports", ["scan_id"], unique=False)
    op.create_index(op.f("ix_reports_generated_by"), "reports", ["generated_by"], unique=False)

    # 8. Table: audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_entity_type"), "audit_log", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_log_entity_id"), "audit_log", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("reports")
    op.drop_table("violations")
    op.drop_table("extractions")
    op.drop_table("scans")
    op.drop_table("products")
    op.drop_table("users")
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm";')
