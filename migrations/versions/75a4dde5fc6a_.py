"""empty message

Revision ID: 75a4dde5fc6a
Revises: 5ef82566016f
Create Date: 2023-03-27 12:44:48.755094

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '75a4dde5fc6a'
down_revision = '5ef82566016f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client', sa.Column('tagline', sa.String(), nullable=True))
    op.add_column('client', sa.Column('description', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client', 'description')
    op.drop_column('client', 'tagline')
    # ### end Alembic commands ###
