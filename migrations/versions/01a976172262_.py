"""Added prospect_location, company_location, and blocks

Revision ID: 01a976172262
Revises: 7abecf0b7bce
Create Date: 2024-01-17 16:07:16.797034

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "01a976172262"
down_revision = "7abecf0b7bce"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "prospect", sa.Column("prospect_location", sa.String(), nullable=True)
    )
    op.add_column("prospect", sa.Column("company_location", sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "company_location")
    op.drop_column("prospect", "prospect_location")
    # ### end Alembic commands ###