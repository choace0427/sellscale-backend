"""Removed client_sdr_id from bump_framework

Revision ID: d86122449acf
Revises: aadc9b2000f9
Create Date: 2023-04-01 17:45:28.827885

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d86122449acf"
down_revision = "aadc9b2000f9"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "bump_framework_client_sdr_id_fkey", "bump_framework", type_="foreignkey"
    )
    op.drop_column("bump_framework", "client_sdr_id")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "bump_framework",
        sa.Column("client_sdr_id", sa.INTEGER(), autoincrement=False, nullable=False),
    )
    op.create_foreign_key(
        "bump_framework_client_sdr_id_fkey",
        "bump_framework",
        "client_sdr",
        ["client_sdr_id"],
        ["id"],
    )
    # ### end Alembic commands ###
