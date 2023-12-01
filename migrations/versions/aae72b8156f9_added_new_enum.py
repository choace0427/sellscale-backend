"""Added new enum

Revision ID: aae72b8156f9
Revises: cdd787d0776d
Create Date: 2023-11-30 11:13:34.220978

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, MetaData

# revision identifiers, used by Alembic.
revision = 'aae72b8156f9'
down_revision = 'cdd787d0776d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'research_payload' AND column_name = 'research_type'").fetchone()
    enum_type_name = result[0]
    
    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]
    
    # Add the new value to the enum type
    values.append('CUSTOM_DATA')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'CUSTOM_DATA'))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'research_payload' AND column_name = 'research_type'").fetchone()
    enum_type_name = result[0]
    
    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'CUSTOM_DATA'" % enum_type_name)
    # ### end Alembic commands ###