"""Added Review Segment Enum

Revision ID: 11c476b47cdd
Revises: 6c9a26d736df
Create Date: 2024-02-01 11:14:04.545416

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "11c476b47cdd"
down_revision = "6c9a26d736df"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'REVIEW_SEGMENT'")


def downgrade():
    pass
