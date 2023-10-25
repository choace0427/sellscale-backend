"""Add account.invalid type to Nylas Webhook types

Revision ID: 34febb8ae080
Revises: a8854c87d6e2
Create Date: 2023-10-25 15:13:08.188441

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '34febb8ae080'
down_revision = 'a8854c87d6e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE nylaswebhooktype ADD VALUE 'ACCOUNT_INVALID'")

def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DELETE FROM pg_enum WHERE enumlabel = 'account.invalid' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'nylaswebhooktype')")
