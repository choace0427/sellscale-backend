"""Added Enrich Segment Enum

Revision ID: 6c9a26d736df
Revises: 8805c5367d65
Create Date: 2024-01-31 10:45:21.612887

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6c9a26d736df"
down_revision = "8805c5367d65"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'ENRICH_SEGMENT'")


def downgrade():
    pass
