"""Make columns nullable count_ctas and count_bumps

Revision ID: da35007163ae
Revises: b613521284d3
Create Date: 2024-07-30 18:47:49.385230

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'da35007163ae'
down_revision = 'b613521284d3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('internal_default_voices', 'count_ctas',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('internal_default_voices', 'count_bumps',
               existing_type=sa.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('internal_default_voices', 'count_bumps',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('internal_default_voices', 'count_ctas',
               existing_type=sa.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###