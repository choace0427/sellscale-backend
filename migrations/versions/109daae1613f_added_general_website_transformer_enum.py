"""Added General Website Transformer Enum

Revision ID: 109daae1613f
Revises: 08f01ee8565f
Create Date: 2022-11-01 17:15:19.924107

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "109daae1613f"
down_revision = "08f01ee8565f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'GENERAL_WEBSITE_TRANSFORMER'")


def downgrade():
    pass
