"""Added Both Email/Linkedin Campaign Review Task

Revision ID: 41e2b87d9e06
Revises: b5ee1948a195
Create Date: 2024-04-22 18:18:52.889374

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41e2b87d9e06'
down_revision = 'b5ee1948a195'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'BOTH_CAMPAIGN_REVIEW'")


def downgrade():
    pass
