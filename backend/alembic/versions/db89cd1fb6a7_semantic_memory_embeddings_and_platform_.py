"""semantic memory embeddings and platform ingestion fields

Revision ID: db89cd1fb6a7
Revises: 081c622bc712
Create Date: 2026-09-11 17:45:45.003856

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'db89cd1fb6a7'
down_revision: Union[str, None] = '081c622bc712'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Switch from the unused 1536-dim (OpenAI) column to the 384-dim local
    # embedding model actually wired up (app/agent_service/memory/
    # embeddings.py). Nothing has ever written a row to this table yet
    # (README: "nothing writes or queries it"), so there's no data to
    # migrate — a straight type change is safe.
    op.alter_column(
        "content_embeddings",
        "embedding",
        type_=Vector(384),
        postgresql_using="NULL",
    )

    op.add_column("social_accounts", sa.Column("url", sa.String(), nullable=True))
    op.add_column("social_accounts", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("content_items", sa.Column("external_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_content_items_external_id"), "content_items", ["external_id"], unique=False)
    op.add_column("content_items", sa.Column("external_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("content_items", "external_url")
    op.drop_index(op.f("ix_content_items_external_id"), table_name="content_items")
    op.drop_column("content_items", "external_id")

    op.drop_column("social_accounts", "last_synced_at")
    op.drop_column("social_accounts", "url")

    op.alter_column(
        "content_embeddings",
        "embedding",
        type_=Vector(1536),
        postgresql_using="NULL",
    )
