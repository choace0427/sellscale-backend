"""Rename client_archetype_assets to assets

Revision ID: a33c7e209662
Revises: 2d543f74ed52
Create Date: 2024-02-29 14:49:12.144430

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a33c7e209662"
down_revision = "2d543f74ed52"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("client_archetype_assets", "client_assets")
    pass


def downgrade():
    op.rename_table("client_assets", "client_archetype_assets")
    pass
