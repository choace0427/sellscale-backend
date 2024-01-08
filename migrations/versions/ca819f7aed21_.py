"""added segment table

Revision ID: ca819f7aed21
Revises: a453cff36242
Create Date: 2024-01-05 10:37:23.620127

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ca819f7aed21"
down_revision = "a453cff36242"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "segment",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_sdr_id", sa.Integer(), nullable=True),
        sa.Column("segment_title", sa.String(length=255), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_sdr_id"],
            ["client_sdr.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("segment")
    # ### end Alembic commands ###