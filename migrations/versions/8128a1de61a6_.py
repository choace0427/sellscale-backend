"""This migration will add the phone number column and reveal_phone_number column to the prospect table.

Revision ID: 8128a1de61a6
Revises: 17713c0655da
Create Date: 2024-07-25 16:08:40.650362

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8128a1de61a6'
down_revision = '17713c0655da'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect', sa.Column('reveal_phone_number', sa.Boolean(), nullable=True))
    op.add_column('prospect', sa.Column('phone_number', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect', 'phone_number')
    op.drop_column('prospect', 'reveal_phone_number')
    # ### end Alembic commands ###
