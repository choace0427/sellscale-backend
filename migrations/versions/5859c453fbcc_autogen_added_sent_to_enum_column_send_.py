"""Autogen - Added SENT to enum column send_status in table generated_message_auto_bump

Revision ID: 5859c453fbcc
Revises: bbe50bc63ea4
Create Date: 2023-07-13 13:41:26.894485

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5859c453fbcc'
down_revision = 'bbe50bc63ea4'
branch_labels = None
depends_on = None


def upgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'generated_message_auto_bump' AND column_name = 'send_status'").fetchone()
    enum_type_name = result[0]

    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]

    # Add the new value to the enum type
    values.append('SENT')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'SENT'))
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'generated_message_auto_bump' AND column_name = 'send_status'").fetchone()
    enum_type_name = result[0]

    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'SENT'" % enum_type_name)
    pass
