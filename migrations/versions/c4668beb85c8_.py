"""empty message

Revision ID: c4668beb85c8
Revises: ad353a0fa3ad
Create Date: 2024-07-11 12:14:38.219388

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4668beb85c8'
down_revision = 'ad353a0fa3ad'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('crm_contact', sa.Column('do_not_contact', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('crm_contact', 'do_not_contact')
    # ### end Alembic commands ###
