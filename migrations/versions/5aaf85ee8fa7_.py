""" Add icp_matching_credits to client_sdr

Revision ID: 5aaf85ee8fa7
Revises: 8ff044fd54ba
Create Date: 2023-04-07 12:54:06.266038

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5aaf85ee8fa7'
down_revision = '8ff044fd54ba'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('icp_matching_credits', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'icp_matching_credits')
    # ### end Alembic commands ###
