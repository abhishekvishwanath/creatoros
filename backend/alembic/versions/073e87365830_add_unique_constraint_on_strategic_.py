"""add unique constraint on strategic_learnings creator category

Revision ID: 073e87365830
Revises: 0df29313a212
Create Date: 2026-09-09 21:27:43.846536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '073e87365830'
down_revision: Union[str, None] = '0df29313a212'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_strategic_learnings_creator_category", "strategic_learnings", ["creator_id", "category"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_strategic_learnings_creator_category", "strategic_learnings", type_="unique")
