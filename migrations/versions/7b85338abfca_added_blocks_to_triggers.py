"""Added blocks to triggers

Revision ID: 7b85338abfca
Revises: 5fca5c77e7e7
Create Date: 2023-11-27 16:19:49.779830

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b85338abfca'
down_revision = '5fca5c77e7e7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('trigger', sa.Column('keyword_blacklist', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('trigger', 'keyword_blacklist')
    # ### end Alembic commands ###
