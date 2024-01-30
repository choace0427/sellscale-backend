"""Added Create Pre Filter Type to Operator Dashboard Task Types

Revision ID: 8441065b7efd
Revises: 284f18b26458
Create Date: 2024-01-30 14:43:44.196213

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8441065b7efd"
down_revision = "284f18b26458"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'CREATE_PREFILTERS'")


def downgrade():
    pass
