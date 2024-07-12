"""Added active to icp_routing

Revision ID: 074ff15a4edf
Revises: 8156ab4941a6
Create Date: 2024-07-11 17:46:10.814691

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '074ff15a4edf'
down_revision = '8156ab4941a6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('icp_routing', sa.Column('active', sa.Boolean(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('icp_routing', 'active')
    # ### end Alembic commands ###
