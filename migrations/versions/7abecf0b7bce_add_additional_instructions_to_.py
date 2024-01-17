"""Add additional_instructions to BumpFramework

Revision ID: 7abecf0b7bce
Revises: 667474cfa1ce
Create Date: 2024-01-17 10:58:48.672984

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7abecf0b7bce"
down_revision = "667474cfa1ce"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "bump_framework",
        sa.Column("additional_instructions", sa.String(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("bump_framework", "additional_instructions")
    # ### end Alembic commands ###
