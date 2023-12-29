"""Add Active Convo Queued for Snooze

Revision ID: 27d1778a372a
Revises: 1af370173391
Create Date: 2023-12-28 18:24:05.017415

"""
from alembic import op
from sqlalchemy import Table, MetaData
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27d1778a372a"
down_revision = "1af370173391"
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
    values.append("ACTIVE_CONVO_QUEUED_FOR_SNOOZE")
    op.execute(
        "ALTER TYPE %s ADD VALUE '%s'"
        % (enum_type_name, "ACTIVE_CONVO_QUEUED_FOR_SNOOZE")
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
    op.execute(
        "ALTER TYPE %s DROP VALUE 'ACTIVE_CONVO_QUEUED_FOR_SNOOZE'" % enum_type_name
    )
    pass
