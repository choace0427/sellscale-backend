"""Adding active column to domain, defaults to True

Revision ID: 1a1de7b30e5c
Revises: ca27928e5c09
Create Date: 2024-07-18 00:22:17.932872

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1a1de7b30e5c'
down_revision = 'ca27928e5c09'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('domain', sa.Column('active', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('domain', 'active')
    # ### end Alembic commands ###
