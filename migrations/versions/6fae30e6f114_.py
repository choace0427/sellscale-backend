"""Added merge_crm_account_token and blocks

Revision ID: 6fae30e6f114
Revises: 85a76109779c
Create Date: 2024-01-25 22:16:23.382314

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6fae30e6f114"
down_revision = "85a76109779c"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client", sa.Column("merge_crm_account_token", sa.String(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client", "merge_crm_account_token")
    # ### end Alembic commands ###