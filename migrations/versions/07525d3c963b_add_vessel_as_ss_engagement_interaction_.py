"""Add Vessel as SS Engagement Interaction Source

Revision ID: 07525d3c963b
Revises: 87325abf54cf
Create Date: 2023-03-01 11:45:27.494427

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "07525d3c963b"
down_revision = "87325abf54cf"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE salesengagementinteractionsource ADD VALUE 'VESSEL'")


def downgrade():
    pass
