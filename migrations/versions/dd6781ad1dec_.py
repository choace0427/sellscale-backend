""" Merge heads

Revision ID: dd6781ad1dec
Revises: c78b2b8520ad, e51c943d4e4e
Create Date: 2023-05-26 10:01:23.493327

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd6781ad1dec'
down_revision = ('c78b2b8520ad', 'e51c943d4e4e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
