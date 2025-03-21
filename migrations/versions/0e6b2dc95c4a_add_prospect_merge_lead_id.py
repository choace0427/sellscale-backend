"""Add prospect.merge_lead_id

Revision ID: 0e6b2dc95c4a
Revises: 41e2b87d9e06
Create Date: 2024-04-24 15:02:44.286744

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0e6b2dc95c4a"
down_revision = "41e2b87d9e06"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("prospect", sa.Column("merge_lead_id", sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "merge_lead_id")
    # ### end Alembic commands ###
