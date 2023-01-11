"""Added is_lead to prospect table

Revision ID: bb6e3ed031bf
Revises: 22b58d266211
Create Date: 2023-01-10 14:58:26.607866

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bb6e3ed031bf"
down_revision = "22b58d266211"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("prospect", sa.Column("is_lead", sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "is_lead")
    # ### end Alembic commands ###
