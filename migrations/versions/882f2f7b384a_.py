"""Added weekly_email_outbound_target to client_sdr

Revision ID: 882f2f7b384a
Revises: c8ce70936a23
Create Date: 2023-01-03 14:17:27.065057

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "882f2f7b384a"
down_revision = "c8ce70936a23"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_sdr",
        sa.Column("weekly_email_outbound_target", sa.Integer(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client_sdr", "weekly_email_outbound_target")
    # ### end Alembic commands ###
