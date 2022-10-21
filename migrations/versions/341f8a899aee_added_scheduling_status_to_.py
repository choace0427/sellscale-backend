"""Added Scheduling Status to ProspectStatus

Revision ID: 341f8a899aee
Revises: 9e34e68298c0
Create Date: 2022-10-21 12:17:44.225316

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "341f8a899aee"
down_revision = "9e34e68298c0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE prospectstatus ADD VALUE 'SCHEDULING'")


def downgrade():
    pass
