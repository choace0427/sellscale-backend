"""Added new columns to outbound_campaign table

Revision ID: 3ff85ad67170
Revises: bb6e3ed031bf
Create Date: 2023-01-11 14:50:03.653170

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3ff85ad67170"
down_revision = "bb6e3ed031bf"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "outbound_campaign",
        sa.Column("reported_time_in_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "outbound_campaign", sa.Column("reviewed_feedback", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "outbound_campaign",
        sa.Column("sellscale_grade", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "outbound_campaign",
        sa.Column("brief_feedback_summary", sa.String(), nullable=True),
    )
    op.add_column(
        "outbound_campaign",
        sa.Column("detailed_feedback_link", sa.String(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("outbound_campaign", "detailed_feedback_link")
    op.drop_column("outbound_campaign", "brief_feedback_summary")
    op.drop_column("outbound_campaign", "sellscale_grade")
    op.drop_column("outbound_campaign", "reviewed_feedback")
    op.drop_column("outbound_campaign", "reported_time_in_hours")
    # ### end Alembic commands ###
