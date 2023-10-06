"""Added company industry transformer

Revision ID: 24688361e9cf
Revises: 33104a9d9e38
Create Date: 2023-10-06 14:20:24.627208

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '24688361e9cf'
down_revision = '33104a9d9e38'
branch_labels = None
depends_on = None

def upgrade():
    # Get the name of the enum type associated with the column

    # # Get the current values of the enum type
    # current_values = op.get_bind().execute(
    #     "SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '_researchpointtype')").fetchall()
    # values = [value[0] for value in current_values]

    # # Add the new value to the enum type
    # values.append('CURRENT_JOB_INDUSTRY')
    # op.execute("ALTER TYPE %s ADD VALUE '%s'" %
    #            ('_researchpointtype', 'CURRENT_JOB_INDUSTRY'))
    

    # Get the current values of the enum type
    current_values = op.get_bind().execute(
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'researchpointtype')").fetchall()
    values = [value[0] for value in current_values]

    # Add the new value to the enum type
    values.append('CURRENT_JOB_INDUSTRY')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" %
               ('researchpointtype', 'CURRENT_JOB_INDUSTRY'))


def downgrade():
    # Get the name of the enum type associated with the column
    result = op.get_bind().execute(
        "SELECT udt_name FROM information_schema.columns WHERE table_name = 'bump_framework' AND column_name = 'transformer_blocklist'").fetchone()
    enum_type_name = result[0]

    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'CURRENT_JOB_INDUSTRY'" %
               enum_type_name)
