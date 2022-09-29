"""add more values to research point type

Revision ID: 520bf2c3e0a4
Revises: 122862e737c1
Create Date: 2022-09-29 10:56:05.389697

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "520bf2c3e0a4"
down_revision = "122862e737c1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")

    op.execute("ALTER TYPE gnlpmodeltype ADD VALUE 'TRANSFORMER'")

    pass


def downgrade():
    pass
