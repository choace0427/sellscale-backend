"""Added step_number column to client_asset_archetype_reason_mapping

Revision ID: be60b00401fd
Revises: 8de803f48613
Create Date: 2024-03-08 15:52:28.930101

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "be60b00401fd"
down_revision = "8de803f48613"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_asset_archetype_reason_mapping",
        sa.Column("step_number", sa.Integer(), nullable=True),
    )
    op.drop_column("client_assets", "step_number")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_assets",
        sa.Column("step_number", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.drop_column("client_asset_archetype_reason_mapping", "step_number")
    # ### end Alembic commands ###
