"""Autogen - Added CUSTOM to enum column research_point_type in table research_point

Revision ID: 0fcc7ca9f8e7
Revises: d08f51a78170
Create Date: 2023-06-07 12:00:07.838709

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0fcc7ca9f8e7'
down_revision = 'd08f51a78170'
branch_labels = None
depends_on = None


def upgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'research_point' AND column_name = 'research_point_type'").fetchone()
    enum_type_name = result[0]
    
    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]
    
    # Add the new value to the enum type
    values.append('CUSTOM')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'CUSTOM'))
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'research_point' AND column_name = 'research_point_type'").fetchone()
    enum_type_name = result[0]
    
    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'CUSTOM'" % enum_type_name)
    pass
