"""Added BUMPED

Revision ID: e7465cf48c8a
Revises: 0801ca665ef2
Create Date: 2023-10-03 14:56:42.096961

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, MetaData


# revision identifiers, used by Alembic.
revision = 'e7465cf48c8a'
down_revision = '0801ca665ef2'
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
    values.append('BUMPED')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'BUMPED'))


def downgrade():
    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect_email' AND column_name = 'outreach_status'").fetchone()
    enum_type_name = result[0]
    
    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'BUMPED'" % enum_type_name)
