"""Add email_prospect_replied

Revision ID: b5347b78d23c
Revises: fb39ffe22036
Create Date: 2024-02-08 17:32:22.009197

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b5347b78d23c"
down_revision = "03c6b5aa89d1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE slacknotificationtype ADD VALUE 'EMAIL_PROSPECT_REPLIED'")

    pass


def downgrade():
    op.execute("ALTER TYPE slacknotificationtype DROP VALUE 'EMAIL_PROSPECT_REPLIED'")

    pass
