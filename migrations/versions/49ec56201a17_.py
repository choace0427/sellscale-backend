"""empty message

Revision ID: 49ec56201a17
Revises: 3ff85ad67170
Create Date: 2023-01-11 15:31:54.170152

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '49ec56201a17'
down_revision = '3ff85ad67170'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('outbound_campaign', 'reported_time_in_hours')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('outbound_campaign', sa.Column('reported_time_in_hours', sa.INTEGER(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
