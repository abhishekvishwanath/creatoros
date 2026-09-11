"""add pipeline_runs table

Revision ID: cd14a2497b0e
Revises: db89cd1fb6a7
Create Date: 2026-09-11 18:53:05.560195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd14a2497b0e'
down_revision: Union[str, None] = 'db89cd1fb6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("youtube_url", sa.String(), nullable=True),
        sa.Column("stages", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pipeline_runs_creator_id"), "pipeline_runs", ["creator_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pipeline_runs_creator_id"), table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
