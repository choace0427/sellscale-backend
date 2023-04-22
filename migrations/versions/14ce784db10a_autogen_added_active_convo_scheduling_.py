"""Autogen - Added ACTIVE_CONVO_SCHEDULING to enum column status in table prospect

Revision ID: 14ce784db10a
Revises: 5b692e85658a
Create Date: 2023-04-21 12:40:18.872184

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '14ce784db10a'
down_revision = '5b692e85658a'
branch_labels = None
depends_on = None


def upgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect' AND column_name = 'status'").fetchone()
    enum_type_name = result[0]
    
    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]
    
    # Add the new value to the enum type
    values.append('ACTIVE_CONVO_SCHEDULING')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'ACTIVE_CONVO_SCHEDULING'))
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect' AND column_name = 'status'").fetchone()
    enum_type_name = result[0]
    
    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'ACTIVE_CONVO_SCHEDULING'" % enum_type_name)
    pass
