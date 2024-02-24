"""Added email_sequence_step_to_asset_mapping and blocks to trigger

Revision ID: 3bcdea58d0eb
Revises: 34aad0779519
Create Date: 2024-02-23 12:07:06.924813

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3bcdea58d0eb"
down_revision = "34aad0779519"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "email_sequence_step_to_asset_mapping",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_sequence_step_id", sa.Integer(), nullable=False),
        sa.Column("client_archetype_assets_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_archetype_assets_id"],
            ["client_archetype_assets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["email_sequence_step_id"],
            ["email_sequence_step.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("email_sequence_step_to_asset_mapping")
    # ### end Alembic commands ###