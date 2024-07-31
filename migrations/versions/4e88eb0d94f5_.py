"""empty message

Revision ID: 4e88eb0d94f5
Revises: 4a6d475091eb
Create Date: 2024-07-26 15:31:49.493180

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4e88eb0d94f5'
down_revision = '4a6d475091eb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('saved_apollo_query', sa.Column('is_icp_filter', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('saved_apollo_query', 'is_icp_filter')
    # ### end Alembic commands ###