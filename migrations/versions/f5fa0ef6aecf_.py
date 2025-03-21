"""Added is_champion column to prospect

Revision ID: f5fa0ef6aecf
Revises: d675be6176b6
Create Date: 2024-05-07 14:46:33.492993

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5fa0ef6aecf'
down_revision = 'd675be6176b6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect', sa.Column('is_champion', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect', 'is_champion')
    # ### end Alembic commands ###
