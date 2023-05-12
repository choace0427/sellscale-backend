"""Autogen - Added UNSUBSCRIBED to enum column outreach_status in table prospect_email

Revision ID: efee0d8775a8
Revises: 5a6c83c1e1ca
Create Date: 2023-05-12 11:49:18.067386

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'efee0d8775a8'
down_revision = '5a6c83c1e1ca'
branch_labels = None
depends_on = None


def upgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect_email' AND column_name = 'outreach_status'").fetchone()
    enum_type_name = result[0]

    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]

    # Add the new value to the enum type
    values.append('UNSUBSCRIBED')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'UNSUBSCRIBED'))
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect_email' AND column_name = 'outreach_status'").fetchone()
    enum_type_name = result[0]

    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'UNSUBSCRIBED'" % enum_type_name)
    pass
