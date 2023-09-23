"""Added bump_framework_template_name and bump_framework_human_readable_prompt

Revision ID: 78b66c48d4cc
Revises: e986d39fb0a1
Create Date: 2023-09-19 16:47:37.840880

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "78b66c48d4cc"
down_revision = "e986d39fb0a1"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "bump_framework",
        sa.Column("bump_framework_template_name", sa.String(), nullable=True),
    )
    op.add_column(
        "bump_framework",
        sa.Column("bump_framework_human_readable_prompt", sa.String(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("bump_framework", "bump_framework_human_readable_prompt")
    op.drop_column("bump_framework", "bump_framework_template_name")
    # ### end Alembic commands ###