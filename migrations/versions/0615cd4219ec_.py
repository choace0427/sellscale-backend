"""Added new type to OperatorDashboardTaskType

Revision ID: 0615cd4219ec
Revises: 6e7921c5fe74
Create Date: 2024-01-25 13:28:57.695802

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0615cd4219ec"
down_revision = "6e7921c5fe74"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'SEGMENT_CREATION'")


def downgrade():
    pass
