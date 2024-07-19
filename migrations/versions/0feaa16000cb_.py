"""add value prop and segment description to saved apollo query

Revision ID: 0feaa16000cb
Revises: 3a9df595161a
Create Date: 2024-07-19 16:20:54.786042

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0feaa16000cb'
down_revision = '3a9df595161a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('saved_apollo_query', sa.Column('value_proposition', sa.String(), nullable=True))
    op.add_column('saved_apollo_query', sa.Column('segment_description', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('saved_apollo_query', 'segment_description')
    op.drop_column('saved_apollo_query', 'value_proposition')
    # ### end Alembic commands ###
