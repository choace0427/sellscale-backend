"""Add priority_rating to campaigns and generated_message

Revision ID: 9c1c04b73c5c
Revises: a81be24af31c
Create Date: 2023-07-17 17:06:17.991387

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c1c04b73c5c'
down_revision = 'a81be24af31c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('generated_message', sa.Column('priority_rating', sa.Integer(), nullable=True))
    op.add_column('outbound_campaign', sa.Column('priority_rating', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('outbound_campaign', 'priority_rating')
    op.drop_column('generated_message', 'priority_rating')
    # ### end Alembic commands ###
