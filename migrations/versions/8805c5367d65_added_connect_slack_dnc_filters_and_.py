"""Added Connect Slack, DNC Filters, and Calendar Link Type to OperatorDashboardTaskType

Revision ID: 8805c5367d65
Revises: 8441065b7efd
Create Date: 2024-01-31 09:26:33.850052

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8805c5367d65"
down_revision = "8441065b7efd"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'CONNECT_SLACK'")
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'ADD_DNC_FILTERS'")
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'ADD_CALENDAR_LINK'")


def downgrade():
    pass
