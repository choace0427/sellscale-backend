"""removed  title from bump_framework

Revision ID: 0bb30accd890
Revises: 04ab5ffa9f19
Create Date: 2023-04-04 17:34:56.333401

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0bb30accd890"
down_revision = "04ab5ffa9f19"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("bump_framework", "title")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "bump_framework",
        sa.Column("title", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    )
    # ### end Alembic commands ###
