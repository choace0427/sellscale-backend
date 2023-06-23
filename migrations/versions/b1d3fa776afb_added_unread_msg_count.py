"""Added unread msg count

Revision ID: b1d3fa776afb
Revises: 0fd5007807bc
Create Date: 2023-06-22 20:01:40.298341

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1d3fa776afb'
down_revision = '0fd5007807bc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect', sa.Column('li_unread_messages', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect', 'li_unread_messages')
    # ### end Alembic commands ###
