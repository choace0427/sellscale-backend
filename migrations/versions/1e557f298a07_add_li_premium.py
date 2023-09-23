"""Add li_premium

Revision ID: 1e557f298a07
Revises: eed8e5ca35b5
Create Date: 2023-09-13 15:52:59.708297

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e557f298a07'
down_revision = 'eed8e5ca35b5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('li_premium', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'li_premium')
    # ### end Alembic commands ###