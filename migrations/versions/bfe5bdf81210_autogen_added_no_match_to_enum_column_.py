"""Added ACTIVE_CONVO_REVIVAL to enum column status in table prospect

Revision ID: bfe5bdf81210
Revises: e2ae0b50eb31
Create Date: 2023-06-29 15:01:51.152781

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bfe5bdf81210"
down_revision = "e2ae0b50eb31"
branch_labels = None
depends_on = None


def upgrade():

    # Get the name of the enum type associated with the column
    result = (
        op.get_bind()
        .execute(
            "SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect' AND column_name = 'status'"
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
    values.append("ACTIVE_CONVO_REVIVAL")
    op.execute(
        "ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, "ACTIVE_CONVO_REVIVAL")
    )
    pass


def downgrade():

    # Get the name of the enum type associated with the column
    result = (
        op.get_bind()
        .execute(
            "SELECT udt_name FROM information_schema.columns WHERE table_name = 'prospect' AND column_name = 'status'"
        )
        .fetchone()
    )
    enum_type_name = result[0]

    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE 'ACTIVE_CONVO_REVIVAL'" % enum_type_name)
    pass
