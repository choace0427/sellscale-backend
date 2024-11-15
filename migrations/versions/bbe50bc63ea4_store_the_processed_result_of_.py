"""Store the processed result of SalesNavigatorLaunch

Revision ID: bbe50bc63ea4
Revises: cc0a25be0172
Create Date: 2023-07-13 10:15:45.368868

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'bbe50bc63ea4'
down_revision = 'cc0a25be0172'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('phantom_buster_sales_navigator_launch', 'result', new_column_name='result_raw')
    op.add_column('phantom_buster_sales_navigator_launch', sa.Column('result_processed', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('phantom_buster_sales_navigator_launch', 'result_raw', new_column_name='result')
    op.drop_column('phantom_buster_sales_navigator_launch', 'result_processed')
    # ### end Alembic commands ###
