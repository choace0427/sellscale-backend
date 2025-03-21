"""Add forwarding_enabled to warmup_snapshot

Revision ID: d4ddcb53240f
Revises: 7b1109763147
Create Date: 2023-12-22 17:25:30.899736

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4ddcb53240f"
down_revision = "7b1109763147"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "warmup_snapshot", sa.Column("forwarding_enabled", sa.Boolean(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("warmup_snapshot", "forwarding_enabled")
    # ### end Alembic commands ###
