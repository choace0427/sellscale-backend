"""Autogen - Added QUEUED_FOR_OUTREACH to enum column outreach_status in table prospect_email

Revision ID: 95a6bd43ccd5
Revises: df068549dba0
Create Date: 2023-05-15 13:18:53.201143

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95a6bd43ccd5'
down_revision = 'df068549dba0'
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
    values.append('QUEUED_FOR_OUTREACH')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'QUEUED_FOR_OUTREACH'))
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect_email' AND column_name = 'outreach_status'").fetchone()
    enum_type_name = result[0]
    
    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'QUEUED_FOR_OUTREACH'" % enum_type_name)
    pass
