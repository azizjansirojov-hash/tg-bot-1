"""Initial movies and users tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-07-30 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("file_id", sa.Text(), nullable=False),
        sa.Column("channel_message_id", sa.BigInteger(), nullable=False),
        sa.Column("added_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_movies_code", "movies", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_active",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "request_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("telegram_id"),
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_index("ix_movies_code", table_name="movies")
    op.drop_table("movies")
