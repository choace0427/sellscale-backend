"""Added REP_INTERVENTION_NEEDED

Revision ID: 292bfc6879f6
Revises: d7282ead8c00
Create Date: 2024-03-01 07:25:26.978344

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "292bfc6879f6"
down_revision = "d7282ead8c00"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE operatordashboardtasktype ADD VALUE 'REP_INTERVENTION_NEEDED'"
        )


def downgrade():
    pass
