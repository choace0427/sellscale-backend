"""Added warming details

Revision ID: 1f1860cafcf4
Revises: 2f8aedd174c4
Create Date: 2023-11-16 09:39:10.148252

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f1860cafcf4'
down_revision = '2f8aedd174c4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('warmup_snapshot', sa.Column('warming_details', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('warmup_snapshot', 'warming_details')
    # ### end Alembic commands ###
