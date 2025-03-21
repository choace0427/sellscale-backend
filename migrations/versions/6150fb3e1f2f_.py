"""Added client_archetype_id to voice_builder_onboarding

Revision ID: 6150fb3e1f2f
Revises: 3759b8fd24bc
Create Date: 2023-05-01 15:03:51.550412

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6150fb3e1f2f"
down_revision = "3759b8fd24bc"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "voice_builder_onboarding",
        sa.Column("client_archetype_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        None,
        "voice_builder_onboarding",
        "client_archetype",
        ["client_archetype_id"],
        ["id"],
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "voice_builder_onboarding", type_="foreignkey")
    op.drop_column("voice_builder_onboarding", "client_archetype_id")
    # ### end Alembic commands ###
