"""Add week number into SLA Schedule

Revision ID: 5dd362c163e3
Revises: d28f7a73a937
Create Date: 2023-09-12 10:55:07.420551

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5dd362c163e3'
down_revision = 'd28f7a73a937'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sla_schedule', sa.Column('week', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('sla_schedule', 'week')
    # ### end Alembic commands ###
