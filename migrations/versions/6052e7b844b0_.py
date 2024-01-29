"""empty message

Revision ID: 6052e7b844b0
Revises: 21fa5bd1de00
Create Date: 2024-01-29 14:33:32.010232

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6052e7b844b0"
down_revision = "21fa5bd1de00"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "auto_delete_message_analytics",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("problem", sa.String(), nullable=True),
        sa.Column("prospect", sa.String(), nullable=True),
        sa.Column("sdr_name", sa.String(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("send_date", sa.DateTime(), nullable=True),
        sa.Column("channel", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("auto_delete_message_analytics")
    # ### end Alembic commands ###
