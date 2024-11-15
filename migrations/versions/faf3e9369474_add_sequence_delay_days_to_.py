"""Add sequence delay days to EmailSequenceStep

Revision ID: faf3e9369474
Revises: f0bcb2304f5a
Create Date: 2023-10-17 14:07:44.987886

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'faf3e9369474'
down_revision = 'f0bcb2304f5a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('email_sequence_step', sa.Column('sequence_delay_days', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('email_sequence_step', 'sequence_delay_days')
    # ### end Alembic commands ###
