"""Added results to apollo query

Revision ID: 551857b4589f
Revises: 63e2329969b8
Create Date: 2024-05-20 12:38:22.956838

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '551857b4589f'
down_revision = '63e2329969b8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('saved_apollo_query', sa.Column('results', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('saved_apollo_query', 'results')
    # ### end Alembic commands ###