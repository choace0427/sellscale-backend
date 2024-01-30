"""Added SCHEDULING_FEEDBACK_NEEDED

Revision ID: e660a305a665
Revises: 6052e7b844b0
Create Date: 2024-01-29 16:15:09.456195

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, MetaData

# revision identifiers, used by Alembic.
revision = "e660a305a665"
down_revision = "6052e7b844b0"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE operatordashboardtasktype ADD VALUE 'SCHEDULING_FEEDBACK_NEEDED'"
        )


def downgrade():
    pass
