"""Add email_multichanneled notification

Revision ID: 2a777ce4d04f
Revises: b5347b78d23c
Create Date: 2024-02-08 20:21:03.095992

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a777ce4d04f"
down_revision = "b5347b78d23c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE slacknotificationtype ADD VALUE 'EMAIL_MULTICHANNELED'")

    pass


def downgrade():
    op.execute("ALTER TYPE slacknotificationtype DROP VALUE 'EMAIL_MULTICHANNELED'")

    pass
