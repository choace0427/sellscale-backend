"""add approved as field to generate d message status

Revision ID: 011d80650150
Revises: 3117503de947
Create Date: 2022-09-29 16:32:44.023368

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "011d80650150"
down_revision = "3117503de947"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")

    op.execute("ALTER TYPE generatedmessagestatus ADD VALUE 'APPROVED'")


def downgrade():
    pass
