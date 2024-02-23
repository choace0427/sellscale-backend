"""times_replied, smartlead_sent_count, date_sent

Revision ID: bcd59e1cead5
Revises: 3bcdea58d0eb
Create Date: 2024-02-23 13:34:46.616265

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bcd59e1cead5"
down_revision = "3bcdea58d0eb"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "email_messaging_schedule", sa.Column("date_sent", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "email_sequence_step", sa.Column("times_replied", sa.Integer(), nullable=True)
    )
    op.add_column(
        "prospect_email", sa.Column("smartlead_sent_count", sa.Integer(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect_email", "smartlead_sent_count")
    op.drop_column("email_sequence_step", "times_replied")
    op.drop_column("email_messaging_schedule", "date_sent")
    # ### end Alembic commands ###
