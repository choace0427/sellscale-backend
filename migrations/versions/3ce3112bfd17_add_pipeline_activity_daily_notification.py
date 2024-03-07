"""Add Pipeline Activity Daily notification

Revision ID: 3ce3112bfd17
Revises: 53ecb4f66b11
Create Date: 2024-03-07 12:24:48.498870

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3ce3112bfd17"
down_revision = "53ecb4f66b11"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE slacknotificationtype ADD VALUE 'PIPELINE_ACTIVITY_DAILY'")

    pass


def downgrade():
    op.execute("ALTER TYPE slacknotificationtype DROP VALUE 'PIPELINE_ACTIVITY_DAILY'")

    pass
