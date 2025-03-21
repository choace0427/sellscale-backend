"""Add li_at_token to Client SDR for Phantoms

Revision ID: 46bdde25829b
Revises: 81e2f10b7ad7
Create Date: 2023-01-12 12:09:28.403968

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '46bdde25829b'
down_revision = '81e2f10b7ad7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('li_at_token', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'li_at_token')
    # ### end Alembic commands ###
