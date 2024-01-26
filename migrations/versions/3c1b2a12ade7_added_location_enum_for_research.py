"""Added location enum for research

Revision ID: 3c1b2a12ade7
Revises: 982ad11490c7
Create Date: 2024-01-24 17:57:38.034392

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, MetaData


# revision identifiers, used by Alembic.
revision = "3c1b2a12ade7"
down_revision = "982ad11490c7"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # Get the name of the enum type associated with the column
    result = (
        op.get_bind()
        .execute(
            "SELECT udt_name FROM information_schema.columns WHERE table_name = 'research_point' AND column_name = 'research_point_type'"
        )
        .fetchone()
    )
    enum_type_name = result[0]

    # Get the current values of the enum type
    current_values = (
        op.get_bind()
        .execute(
            "SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')"
            % enum_type_name
        )
        .fetchall()
    )
    values = [value[0] for value in current_values]

    # Add the new value to the enum type
    values.append("CURRENT_LOCATION")
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, "CURRENT_LOCATION"))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###