"""Add Serp Payload and Point Types

Revision ID: a02d3a083c12
Revises: b2af7c17975d
Create Date: 2023-01-06 11:59:20.220360

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a02d3a083c12"
down_revision = "b2af7c17975d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'SERP_NEWS_SUMMARY'")
    op.execute("ALTER TYPE researchtype ADD VALUE 'SERP_PAYLOAD'")


def downgrade():
    pass
