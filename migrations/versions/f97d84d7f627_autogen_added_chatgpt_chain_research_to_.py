"""Autogen - Added CHATGPT_CHAIN_RESEARCH to enum column account_research_type in table account_research_point

Revision ID: f97d84d7f627
Revises: 6150fb3e1f2f
Create Date: 2023-05-02 14:18:54.142295

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f97d84d7f627'
down_revision = '6150fb3e1f2f'
branch_labels = None
depends_on = None


def upgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'account_research_point' AND column_name = 'account_research_type'").fetchone()
    enum_type_name = result[0]

    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]

    # Add the new value to the enum type
    values.append('CHATGPT_CHAIN_RESEARCH')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, 'CHATGPT_CHAIN_RESEARCH'))
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = 'account_research_point' AND column_name = 'account_research_type'").fetchone()
    enum_type_name = result[0]

    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'CHATGPT_CHAIN_RESEARCH'" % enum_type_name)
    pass
