"""Add is_daily_generation to campaign

Revision ID: fbad6e3cbc0b
Revises: f2e501b27cfc
Create Date: 2023-11-14 10:19:21.618115

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fbad6e3cbc0b'
down_revision = 'f2e501b27cfc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('outbound_campaign', sa.Column('is_daily_generation', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('outbound_campaign', 'is_daily_generation')
    # ### end Alembic commands ###
