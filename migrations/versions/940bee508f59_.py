"""add icp_routing_id to prospect

Revision ID: 940bee508f59
Revises: ff3e72a0db1c
Create Date: 2024-07-29 10:34:34.423814

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '940bee508f59'
down_revision = 'ff3e72a0db1c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('prospect', sa.Column('icp_routing_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'prospect', 'icp_routing', ['icp_routing_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'prospect', type_='foreignkey')
    op.drop_column('prospect', 'icp_routing_id')
    # ### end Alembic commands ###
