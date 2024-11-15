"""Added weekly report cc and bcc emails

Revision ID: 40e423648549
Revises: 8da7d9beb704
Create Date: 2023-10-13 15:44:27.097037

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "40e423648549"
down_revision = "8da7d9beb704"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_sdr",
        sa.Column("weekly_report_cc_emails", sa.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "client_sdr",
        sa.Column("weekly_report_bcc_emails", sa.ARRAY(sa.String()), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client_sdr", "weekly_report_bcc_emails")
    op.drop_column("client_sdr", "weekly_report_cc_emails")
    # ### end Alembic commands ###
