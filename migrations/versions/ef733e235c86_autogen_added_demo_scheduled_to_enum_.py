"""Autogen - Added DEMO_SCHEDULED to enum column hidden_reason in table prospect

Revision ID: ef733e235c86
Revises: 0337ae539b75
Create Date: 2023-05-10 15:51:49.137002

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef733e235c86'
down_revision = '0337ae539b75'
branch_labels = None
depends_on = None


def upgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect' AND column_name = 'hidden_reason'").fetchone()
    enum_type_name = result[0]
    
    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]
    
    # Add the new value to the enum type
    values.append('DEMO_SCHEDULED')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'DEMO_SCHEDULED'))
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect' AND column_name = 'hidden_reason'").fetchone()
    enum_type_name = result[0]
    
    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'DEMO_SCHEDULED'" % enum_type_name)
    pass
