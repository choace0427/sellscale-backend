"""Added last_msg_from_sdr

Revision ID: 9d8a7460abba
Revises: 16d43d11a4b3
Create Date: 2023-06-26 11:06:39.460066

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d8a7460abba'
down_revision = '16d43d11a4b3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect', sa.Column('li_last_message_from_sdr', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect', 'li_last_message_from_sdr')
    # ### end Alembic commands ###
