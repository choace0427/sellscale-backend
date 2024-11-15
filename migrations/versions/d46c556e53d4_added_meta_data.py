"""Added meta_data

Revision ID: d46c556e53d4
Revises: fbad6e3cbc0b
Create Date: 2023-11-14 16:24:41.026604

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd46c556e53d4'
down_revision = 'fbad6e3cbc0b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('meta_data', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'meta_data')
    # ### end Alembic commands ###
