"""Added Review AI Brain Task

Revision ID: 10e435da39b7
Revises: de87abe4bbcf
Create Date: 2024-04-02 12:07:39.750072

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '10e435da39b7'
down_revision = 'de87abe4bbcf'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'REVIEW_AI_BRAIN'")

def downgrade():
    pass
