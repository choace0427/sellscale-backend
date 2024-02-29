"""asset_created

Revision ID: 2d543f74ed52
Revises: cff6d11e1f59
Create Date: 2024-02-28 16:53:45.121119

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2d543f74ed52"
down_revision = "cff6d11e1f59"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE slacknotificationtype ADD VALUE 'ASSET_CREATED'")

    pass


def downgrade():
    op.execute("ALTER TYPE slacknotificationtype DROP VALUE 'ASSET_CREATED'")

    pass
