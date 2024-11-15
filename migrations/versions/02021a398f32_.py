"""Add `flagged` to research_point

Revision ID: 02021a398f32
Revises: a14d7226c9c4
Create Date: 2022-11-23 15:36:50.059269

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "02021a398f32"
down_revision = "a14d7226c9c4"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("research_point", sa.Column("flagged", sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("research_point", "flagged")
    # ### end Alembic commands ###
