"""add unique constraint on script content_item_id + version_number

Revision ID: 2f40fdeacbcd
Revises: 02b0466c5b7a
Create Date: 2026-09-08 12:27:20.949143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f40fdeacbcd'
down_revision: Union[str, None] = '02b0466c5b7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_scripts_content_item_version", "scripts", ["content_item_id", "version_number"])


def downgrade() -> None:
    op.drop_constraint("uq_scripts_content_item_version", "scripts", type_="unique")
