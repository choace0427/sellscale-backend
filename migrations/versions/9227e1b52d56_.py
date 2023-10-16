"""Added human_feedback to bump_framework

Revision ID: 9227e1b52d56
Revises: 943ffb4cbb31
Create Date: 2023-10-15 21:31:12.318759

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9227e1b52d56"
down_revision = "943ffb4cbb31"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "bump_framework", sa.Column("human_feedback", sa.String(), nullable=True)
    )
    op.alter_column(
        "bump_framework_templates", "tag", existing_type=sa.VARCHAR(), nullable=True
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "bump_framework_templates", "tag", existing_type=sa.VARCHAR(), nullable=False
    )
    op.drop_column("bump_framework", "human_feedback")
    # ### end Alembic commands ###
