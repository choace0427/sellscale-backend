"""Add INITIAL_EDIT_COMPLETE

Revision ID: b9810fddf233
Revises: 16853d25c66e
Create Date: 2022-12-20 17:22:01.309885

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b9810fddf233"
down_revision = "16853d25c66e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE outboundcampaignstatus ADD VALUE 'INITIAL_EDIT_COMPLETE'")


def downgrade():
    pass
