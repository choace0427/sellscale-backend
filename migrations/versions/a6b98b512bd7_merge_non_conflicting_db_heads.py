"""Merge non-conflicting db heads

Revision ID: a6b98b512bd7
Revises: b2cbebbdb727, b9810fddf233
Create Date: 2022-12-21 11:15:09.889316

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6b98b512bd7'
down_revision = ('b2cbebbdb727', 'b9810fddf233')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
