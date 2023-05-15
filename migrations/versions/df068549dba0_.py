"""empty message

Revision ID: df068549dba0
Revises: 25d98ee3ad41
Create Date: 2023-05-15 13:15:13.908432

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df068549dba0'
down_revision = '25d98ee3ad41'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect_email', sa.Column('date_scheduled_to_send', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect_email', 'date_scheduled_to_send')
    # ### end Alembic commands ###
