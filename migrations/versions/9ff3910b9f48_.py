""" Add common education to research point type

Revision ID: 9ff3910b9f48
Revises: f38128d3d4ae
Create Date: 2023-03-09 17:23:12.631871

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9ff3910b9f48'
down_revision = 'f38128d3d4ae'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'COMMON_EDUCATION'")
    pass


def downgrade():
    pass
