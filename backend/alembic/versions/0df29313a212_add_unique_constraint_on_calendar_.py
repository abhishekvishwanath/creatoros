"""add unique constraint on calendar_events content_item_id

Revision ID: 0df29313a212
Revises: 2f40fdeacbcd
Create Date: 2026-09-09 19:40:14.653290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0df29313a212'
down_revision: Union[str, None] = '2f40fdeacbcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_calendar_events_content_item", "calendar_events", ["content_item_id"])


def downgrade() -> None:
    op.drop_constraint("uq_calendar_events_content_item", "calendar_events", type_="unique")
