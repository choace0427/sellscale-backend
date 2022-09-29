"""empty message

Revision ID: dcc232b5aee1
Revises: c35cfce54e46
Create Date: 2022-09-29 14:09:32.291866

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dcc232b5aee1'
down_revision = 'c35cfce54e46'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'prospect', 'client', ['client_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'prospect', type_='foreignkey')
    op.drop_column('prospect', 'client_id')
    # ### end Alembic commands ###
