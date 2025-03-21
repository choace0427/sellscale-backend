"""add widget_type to selix_session

Revision ID: e67f50d2d3ad
Revises: 9e4757c6eff6
Create Date: 2024-08-22 11:29:52.601041

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e67f50d2d3ad'
down_revision = '9e4757c6eff6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('selix_session', sa.Column('widget_type', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('selix_session', 'widget_type')
    # ### end Alembic commands ###
