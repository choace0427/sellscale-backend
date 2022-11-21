"""Add READY_TO_SEND

Revision ID: a14d7226c9c4
Revises: fcb542581cf6
Create Date: 2022-11-20 20:04:50.846091

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a14d7226c9c4"
down_revision = "fcb542581cf6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE outboundcampaignstatus ADD VALUE 'READY_TO_SEND'")


def downgrade():
    pass
