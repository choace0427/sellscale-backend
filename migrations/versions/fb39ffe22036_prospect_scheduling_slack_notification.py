"""Add LINKEDIN_PROSPECT_SCHEDULING Notification

Revision ID: fb39ffe22036
Revises: 7afc2ac47f89
Create Date: 2024-02-06 15:35:19.528410

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fb39ffe22036"
down_revision = "a38bc644ee69"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TYPE slacknotificationtype ADD VALUE 'LINKEDIN_PROSPECT_SCHEDULING'"
    )

    pass


def downgrade():
    op.execute(
        "ALTER TYPE slacknotificationtype DROP VALUE 'LINKEDIN_PROSPECT_SCHEDULING'"
    )

    pass
