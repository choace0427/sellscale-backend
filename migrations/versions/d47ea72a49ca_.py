"""Added chat_bot_data_repository table

Revision ID: d47ea72a49ca
Revises: 11c476b47cdd
Create Date: 2024-02-01 15:50:52.116524

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d47ea72a49ca"
down_revision = "11c476b47cdd"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "chat_bot_data_repository",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_sdr_id", sa.Integer(), nullable=True),
        sa.Column("usage_analytics_data", sa.JSON(), nullable=True),
        sa.Column("tam_graph_data", sa.JSON(), nullable=True),
        sa.Column("rejection_report_data", sa.JSON(), nullable=True),
        sa.Column("demo_feedback_data", sa.JSON(), nullable=True),
        sa.Column("message_analytics_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_sdr_id"],
            ["client_sdr.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("chat_bot_data_repository")
    # ### end Alembic commands ###
