"""Added GeneratedMessageEditRecord

Revision ID: 8f53719b2159
Revises: 470dcce7d954
Create Date: 2023-01-07 22:25:28.812194

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8f53719b2159"
down_revision = "470dcce7d954"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "generated_message_edit_record",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generated_message_id", sa.Integer(), nullable=False),
        sa.Column("original_text", sa.String(), nullable=False),
        sa.Column("edited_text", sa.String(), nullable=False),
        sa.Column("editor_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["editor_id"],
            ["editor.id"],
        ),
        sa.ForeignKeyConstraint(
            ["generated_message_id"],
            ["generated_message.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("generated_message_edit_record")
    # ### end Alembic commands ###
