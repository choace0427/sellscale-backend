"""Add NOT_STARTED to StrategyStatuses enum

Revision ID: 7512751dda23
Revises: 74f9a5bf3133
Create Date: 2024-07-16 12:20:34.433116

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7512751dda23'
down_revision = '74f9a5bf3133'
branch_labels = None
depends_on = None


def upgrade():
    # Add the new value to the enum type
    op.execute("ALTER TYPE strategystatuses ADD VALUE 'NOT_STARTED'")


def downgrade():
    # Note: Downgrading an enum type is not straightforward and may require more complex operations
    pass