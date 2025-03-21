""" Add nylas_thread_id to prospect_email

Revision ID: fb790d01bce6
Revises: f97d84d7f627
Create Date: 2023-05-03 15:09:14.467203

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fb790d01bce6'
down_revision = 'f97d84d7f627'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect_email', sa.Column('nylas_thread_id', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect_email', 'nylas_thread_id')
    # ### end Alembic commands ###
