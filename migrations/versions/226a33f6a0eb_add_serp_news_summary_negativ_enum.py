"""Add SERP News Summary Negativ Enum

Revision ID: 226a33f6a0eb
Revises: 601320b93d78
Create Date: 2023-02-10 10:12:57.462883

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "226a33f6a0eb"
down_revision = "601320b93d78"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'SERP_NEWS_SUMMARY_NEGATIVE'")


def downgrade():
    pass
