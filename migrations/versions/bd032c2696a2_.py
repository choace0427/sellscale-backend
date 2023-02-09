"""Added primary composite key to daily_notifications

Revision ID: bd032c2696a2
Revises: 25821adb8ac1
Create Date: 2023-02-09 11:30:17.354007

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bd032c2696a2'
down_revision = '25821adb8ac1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_primary_key(
        "pk_daily_notifications", "daily_notifications",
        ["client_sdr_id", "prospect_id", "type"]
    )
    pass


def downgrade():
    op.drop_constraint("pk_daily_notifications", "daily_notifications")
    pass
