"""Add EMAIL_OPENED and EMAIL_LINK_CLICKED to EngagementFeedType)

Revision ID: f71c5fa9fa2f
Revises: a5e03d9cac6f
Create Date: 2024-05-24 10:39:46.556345

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f71c5fa9fa2f"
down_revision = "a5e03d9cac6f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE engagementfeedtype ADD VALUE 'EMAIL_OPENED'")
    op.execute("ALTER TYPE engagementfeedtype ADD VALUE 'EMAIL_LINK_CLICKED'")
    pass


def downgrade():
    op.execute("ALTER TYPE engagementfeedtype DROP VALUE 'EMAIL_OPENED'")
    op.execute("ALTER TYPE engagementfeedtype DROP VALUE 'EMAIL_LINK_CLICKED'")
    pass
