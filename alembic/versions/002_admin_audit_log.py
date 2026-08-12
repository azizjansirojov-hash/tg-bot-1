"""Add admin_audit_log table.

Revision ID: 002_admin_audit
Revises: 001_initial
Create Date: 2026-08-04 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_admin_audit"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("details", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_audit_log_admin_id",
        "admin_audit_log",
        ["admin_id"],
        unique=False,
    )
    op.create_index(
        "ix_admin_audit_log_timestamp",
        "admin_audit_log",
        ["timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_audit_log_timestamp", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_admin_id", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
