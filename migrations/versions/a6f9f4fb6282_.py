"""Linkedin conversation thread ID

Revision ID: a6f9f4fb6282
Revises: b62c48f79ef7
Create Date: 2022-10-24 09:57:24.879811

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a6f9f4fb6282"
down_revision = "b62c48f79ef7"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "prospect", sa.Column("li_conversation_thread_id", sa.String(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "li_conversation_thread_id")
    # ### end Alembic commands ###
