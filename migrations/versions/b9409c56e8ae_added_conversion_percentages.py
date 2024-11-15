"""Added conversion percentages

Revision ID: b9409c56e8ae
Revises: 03948a4376f9
Create Date: 2023-08-22 15:35:38.424037

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9409c56e8ae'
down_revision = '03948a4376f9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('conversion_percentages', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'conversion_percentages')
    # ### end Alembic commands ###
