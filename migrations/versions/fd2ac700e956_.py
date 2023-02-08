"""Added third composite key to daily notifications: notification type

Revision ID: fd2ac700e956
Revises: d18acc0f8e88
Create Date: 2023-02-08 09:38:39.395879

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fd2ac700e956'
down_revision = 'd18acc0f8e88'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    daily_notifications = postgresql.ENUM(
        "UNKNOWN", "UNREAD_MESSAGE", "NEEDS_BUMP", "SCHEDULING", name="notificationtype"
    )
    daily_notifications.create(op.get_bind())
    op.add_column(
        "daily_notifications",
        sa.Column(
            "type",
            postgresql.ENUM(
                "UNKNOWN",
                "UNREAD_MESSAGE",
                "NEEDS_BUMP",
                "SCHEDULING",
                name="notificationtype",
            ),
            nullable=False,
        ),
    )
    op.alter_column(
        "daily_notifications", "prospect_id", existing_type=sa.INTEGER(), nullable=True
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "daily_notifications", "prospect_id", existing_type=sa.INTEGER(), nullable=False
    )
    op.drop_column("daily_notifications", "type")
    # ### end Alembic commands ###
