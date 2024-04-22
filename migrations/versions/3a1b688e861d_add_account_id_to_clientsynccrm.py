"""Add account_id to ClientSyncCRM

Revision ID: 3a1b688e861d
Revises: 52cabbf81843
Create Date: 2024-04-22 13:44:32.816073

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a1b688e861d"
down_revision = "52cabbf81843"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_sync_crm", sa.Column("account_id", sa.String(), nullable=False)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client_sync_crm", "account_id")
    # ### end Alembic commands ###
