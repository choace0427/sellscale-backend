"""Added Connect Linkedin Task Type

Revision ID: 92c403979a53
Revises: 6fae30e6f114
Create Date: 2024-01-29 09:50:56.045717

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "92c403979a53"
down_revision = "6fae30e6f114"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'CONNECT_LINKEDIN'")


def downgrade():
    pass
