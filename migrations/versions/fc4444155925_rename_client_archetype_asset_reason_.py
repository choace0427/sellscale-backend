"""Rename client_archetype_asset_reason_mapping to client_asset_archetype_reason_mapping

Revision ID: fc4444155925
Revises: a33c7e209662
Create Date: 2024-02-29 15:13:34.263897

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fc4444155925"
down_revision = "a33c7e209662"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table(
        "client_archetype_asset_reason_mapping", "client_asset_archetype_reason_mapping"
    )

    pass


def downgrade():
    op.rename_table(
        "client_asset_archetype_reason_mapping", "client_archetype_asset_reason_mapping"
    )
    pass
