"""Added monthly revenue to client

Revision ID: 7e4ee584d203
Revises: ffc05ba920cb
Create Date: 2023-01-29 18:06:00.627874

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7e4ee584d203"
down_revision = "ffc05ba920cb"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("client", sa.Column("monthly_revenue", sa.Integer(), nullable=True))
    op.drop_column("client_sdr", "monthly_revenue")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_sdr",
        sa.Column("monthly_revenue", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.drop_column("client", "monthly_revenue")
    # ### end Alembic commands ###
