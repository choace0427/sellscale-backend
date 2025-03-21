"""empty message

Revision ID: 4f378421ab4c
Revises: f4caba3dd9de
Create Date: 2022-11-20 14:22:30.319646

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f378421ab4c'
down_revision = 'f4caba3dd9de'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('generated_message', sa.Column('verified_for_send', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('generated_message', 'verified_for_send')
    # ### end Alembic commands ###
