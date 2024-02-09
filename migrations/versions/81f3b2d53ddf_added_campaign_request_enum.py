"""Added Campaign Request Enum



Revision ID: 81f3b2d53ddf
Revises: fb39ffe22036
Create Date: 2024-02-09 10:21:40.329044

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "81f3b2d53ddf"
down_revision = "fb39ffe22036"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operatordashboardtasktype ADD VALUE 'CAMPAIGN_REQUEST'")


def downgrade():
    pass
