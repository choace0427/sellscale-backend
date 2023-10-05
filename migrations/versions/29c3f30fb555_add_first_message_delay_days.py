"""Add first_message_delay_days

Revision ID: 29c3f30fb555
Revises: 105150f27026
Create Date: 2023-09-25 11:45:41.187470

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '29c3f30fb555'
down_revision = '105150f27026'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_archetype', sa.Column('first_message_delay_days', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_archetype', 'first_message_delay_days')
    # ### end Alembic commands ###