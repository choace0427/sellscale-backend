"""Added stack ranked message generation configuration id to generated message

Revision ID: 50e9be559496
Revises: d076167ecfbf
Create Date: 2023-02-07 12:56:56.225090

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "50e9be559496"
down_revision = "d076167ecfbf"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "generated_message",
        sa.Column(
            "stack_ranked_message_generation_configuration_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        None,
        "generated_message",
        "stack_ranked_message_generation_configuration",
        ["stack_ranked_message_generation_configuration_id"],
        ["id"],
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "generated_message", type_="foreignkey")
    op.drop_column(
        "generated_message", "stack_ranked_message_generation_configuration_id"
    )
    # ### end Alembic commands ###
