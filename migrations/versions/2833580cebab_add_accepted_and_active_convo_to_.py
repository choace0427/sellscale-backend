"""Add Accepted and Active Convo to ProspectStatus

Revision ID: 2833580cebab
Revises: be3d64e4be54
Create Date: 2022-10-11 15:41:19.592400

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2833580cebab"
down_revision = "be3d64e4be54"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE prospectstatus ADD VALUE 'ACCEPTED'")
    op.execute("ALTER TYPE prospectstatus ADD VALUE 'ACTIVE_CONVO'")


def downgrade():
    pass
