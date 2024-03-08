"""Added new enum

Revision ID: af1d5045e06f
Revises: 3ce3112bfd17
Create Date: 2024-03-08 08:29:38.694250

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "af1d5045e06f"
down_revision = "3ce3112bfd17"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'VOICE_BUILDER'")


def downgrade():
    pass
