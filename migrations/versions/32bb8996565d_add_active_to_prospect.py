"""Add active to Prospect

Revision ID: 32bb8996565d
Revises: d6814335ece9
Create Date: 2023-07-28 13:01:54.616635

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32bb8996565d'
down_revision = 'd6814335ece9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect', sa.Column('active', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect', 'active')
    # ### end Alembic commands ###