"""Made prospect_id not nullable, use -1 instead

Revision ID: 25821adb8ac1
Revises: f73740d06bcb
Create Date: 2023-02-08 17:01:57.065893

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25821adb8ac1'
down_revision = 'f73740d06bcb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('daily_notifications', 'prospect_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('daily_notifications', 'prospect_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###
