"""Added client_archetype_id to phantom_buster_sales_navigator_launch

Revision ID: b5fa4bdb550f
Revises: 4acbc5cb82e7
Create Date: 2023-09-06 21:43:47.491565

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b5fa4bdb550f"
down_revision = "4acbc5cb82e7"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "phantom_buster_sales_navigator_config_client_archetype_id_fkey",
        "phantom_buster_sales_navigator_config",
        type_="foreignkey",
    )
    op.drop_column("phantom_buster_sales_navigator_config", "client_archetype_id")
    op.add_column(
        "phantom_buster_sales_navigator_launch",
        sa.Column("client_archetype_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        None,
        "phantom_buster_sales_navigator_launch",
        "client_archetype",
        ["client_archetype_id"],
        ["id"],
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        None, "phantom_buster_sales_navigator_launch", type_="foreignkey"
    )
    op.drop_column("phantom_buster_sales_navigator_launch", "client_archetype_id")
    op.add_column(
        "phantom_buster_sales_navigator_config",
        sa.Column(
            "client_archetype_id", sa.INTEGER(), autoincrement=False, nullable=True
        ),
    )
    op.create_foreign_key(
        "phantom_buster_sales_navigator_config_client_archetype_id_fkey",
        "phantom_buster_sales_navigator_config",
        "client_archetype",
        ["client_archetype_id"],
        ["id"],
    )
    # ### end Alembic commands ###