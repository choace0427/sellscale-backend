"""Add generated message instruction model

Revision ID: 74746ecb6f7f
Revises: ee439ecba6e6
Create Date: 2022-12-14 13:02:53.683560

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "74746ecb6f7f"
down_revision = "ee439ecba6e6"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "generated_message_instruction",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("archetype_id", sa.Integer(), nullable=False),
        sa.Column("text_value", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["archetype_id"],
            ["client_archetype.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "generated_message", sa.Column("few_shot_prompt", sa.String(), nullable=True)
    )
    op.add_column(
        "generated_message",
        sa.Column("generated_message_instruction_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        None,
        "generated_message",
        "generated_message_instruction",
        ["generated_message_instruction_id"],
        ["id"],
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "generated_message", type_="foreignkey")
    op.drop_column("generated_message", "generated_message_instruction_id")
    op.drop_column("generated_message", "few_shot_prompt")
    op.drop_table("generated_message_instruction")
    # ### end Alembic commands ###
