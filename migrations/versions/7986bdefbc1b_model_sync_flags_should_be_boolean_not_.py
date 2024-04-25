"""Model Sync Flags should be boolean, not string

Revision ID: 7986bdefbc1b
Revises: f265561d3f4e
Create Date: 2024-04-25 10:55:08.127998

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7986bdefbc1b"
down_revision = "f265561d3f4e"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    # Need to be boolean instead of string
    op.execute(
        "ALTER TABLE client_sync_crm ALTER COLUMN lead_sync TYPE BOOLEAN USING lead_sync::boolean"
    )
    op.execute(
        "ALTER TABLE client_sync_crm ALTER COLUMN contact_sync TYPE BOOLEAN USING contact_sync::boolean"
    )
    op.execute(
        "ALTER TABLE client_sync_crm ALTER COLUMN account_sync TYPE BOOLEAN USING account_sync::boolean"
    )
    op.execute(
        "ALTER TABLE client_sync_crm ALTER COLUMN opportunity_sync TYPE BOOLEAN USING opportunity_sync::boolean"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    # Need to be string instead of boolean
    op.execute(
        "ALTER TABLE client_sync_crm ALTER COLUMN lead_sync TYPE STRING USING lead_sync::string"
    )
    op.execute(
        "ALTER TABLE client_sync_crm ALTER COLUMN contact_sync TYPE STRING USING contact_sync::string"
    )
    op.execute(
        "ALTER TABLE client_sync_crm ALTER COLUMN account_sync TYPE STRING USING account_sync::string"
    )
    op.execute(
        "ALTER TABLE client_sync_crm ALTER COLUMN opportunity_sync TYPE STRING USING opportunity_sync::string"
    )

    # ### end Alembic commands ###