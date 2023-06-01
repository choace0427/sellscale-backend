"""Autogen - Added NO_MATCH to enum column status in table persona_split_request_task

Revision ID: 025d3e740286
Revises: cc6a65a64500
Create Date: 2023-06-01 12:30:43.047249

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '025d3e740286'
down_revision = 'cc6a65a64500'
branch_labels = None
depends_on = None


def upgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'persona_split_request_task' AND column_name = 'status'").fetchone()
    enum_type_name = result[0]
    
    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]
    
    # Add the new value to the enum type
    values.append('NO_MATCH')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'NO_MATCH'))
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'persona_split_request_task' AND column_name = 'status'").fetchone()
    enum_type_name = result[0]
    
    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'NO_MATCH'" % enum_type_name)
    pass
