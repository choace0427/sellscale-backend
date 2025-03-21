"""empty message

Revision ID: 9406464bf9d8
Revises: 074ff15a4edf
Create Date: 2024-07-15 13:50:44.019022

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9406464bf9d8'
down_revision = '074ff15a4edf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('stragegies', sa.Column('start_date', sa.DateTime(), nullable=True))
    op.add_column('stragegies', sa.Column('end_date', sa.DateTime(), nullable=True))
    op.alter_column('stragegies', 'client_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('stragegies', 'created_by',
               existing_type=sa.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('stragegies', 'created_by',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('stragegies', 'client_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_column('stragegies', 'end_date')
    op.drop_column('stragegies', 'start_date')
    # ### end Alembic commands ###
