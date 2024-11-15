"""Added linkedin_conversation_entry table

Revision ID: ffb924852640
Revises: b7a98b640b68
Create Date: 2023-01-16 13:10:07.936729

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ffb924852640"
down_revision = "b7a98b640b68"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "linkedin_conversation_entry",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_url", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("profile_url", sa.String(), nullable=True),
        sa.Column("headline", sa.String(), nullable=True),
        sa.Column("img_url", sa.String(), nullable=True),
        sa.Column("connection_degree", sa.String(), nullable=True),
        sa.Column("li_url", sa.String(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("linkedin_conversation_entry")
    # ### end Alembic commands ###
