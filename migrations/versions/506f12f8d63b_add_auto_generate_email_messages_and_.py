"""Add auto_generate_email_messages and auto_send_email_messages

Revision ID: 506f12f8d63b
Revises: c518fe5f4c61
Create Date: 2023-12-18 11:04:42.865117

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "506f12f8d63b"
down_revision = "c518fe5f4c61"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client", sa.Column("auto_generate_email_messages", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "client", sa.Column("auto_send_email_messages", sa.Boolean(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client", "auto_send_email_messages")
    op.drop_column("client", "auto_generate_email_messages")
    # ### end Alembic commands ###
