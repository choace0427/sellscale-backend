"""Added client_sdr_id to trigger

Revision ID: 2c62d4015f7e
Revises: 09a0819a17e0
Create Date: 2023-11-20 11:18:48.538778

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2c62d4015f7e"
down_revision = "09a0819a17e0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("trigger", sa.Column("client_sdr_id", sa.Integer(), nullable=False))
    op.create_foreign_key(None, "trigger", "client_sdr", ["client_sdr_id"], ["id"])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "trigger", type_="foreignkey")
    op.drop_column("trigger", "client_sdr_id")
    # ### end Alembic commands ###
