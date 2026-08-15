"""Add users.language_code.

Revision ID: 003_user_language
Revises: 002_admin_audit
Create Date: 2026-08-14 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_user_language"
down_revision: Union[str, Sequence[str], None] = "002_admin_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("language_code", sa.String(length=8), nullable=True),
    )
    op.execute(sa.text("UPDATE users SET language_code = 'uz' WHERE language_code IS NULL"))
    op.alter_column(
        "users",
        "language_code",
        existing_type=sa.String(length=8),
        nullable=False,
        server_default="uz",
    )


def downgrade() -> None:
    op.drop_column("users", "language_code")
