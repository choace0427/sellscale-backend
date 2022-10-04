"""empty message

Revision ID: f5a2b0c5b13f
Revises: 3265f54af86c
Create Date: 2022-10-04 16:15:32.628849

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5a2b0c5b13f'
down_revision = '3265f54af86c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('gnlp_models', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'gnlp_models', 'client', ['client_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'gnlp_models', type_='foreignkey')
    op.drop_column('gnlp_models', 'client_id')
    # ### end Alembic commands ###
