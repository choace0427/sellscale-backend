"""Add Client SDR Id as optional to Prospect

Revision ID: b62c48f79ef7
Revises: 75e9aaa0f9bd
Create Date: 2022-10-23 21:26:21.018016

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b62c48f79ef7"
down_revision = "75e9aaa0f9bd"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("prospect", sa.Column("client_sdr_id", sa.Integer(), nullable=True))
    op.create_foreign_key(None, "prospect", "client_sdr", ["client_sdr_id"], ["id"])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "prospect", type_="foreignkey")
    op.drop_column("prospect", "client_sdr_id")
    # ### end Alembic commands ###
