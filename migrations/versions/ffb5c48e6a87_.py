""" Add table constraint, delay days must be positive

Revision ID: ffb5c48e6a87
Revises: faf3e9369474
Create Date: 2023-10-17 14:37:54.664641

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ffb5c48e6a87'
down_revision = 'faf3e9369474'
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        'check_sequence_delay_days_min_value',
        'email_sequence_step',
        'sequence_delay_days >= 0'
    )
    pass


def downgrade():
    op.drop_constraint('check_sequence_delay_days_min_value', 'email_sequence_step')
    pass
