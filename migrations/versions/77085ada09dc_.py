"""Add Queued for Outreach and Send Outreach Failed to Prospect Status

Revision ID: 77085ada09dc
Revises: 75a4dde5fc6a
Create Date: 2023-03-27 13:58:18.068698

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '77085ada09dc'
down_revision = '75a4dde5fc6a'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE prospectstatus ADD VALUE 'QUEUED_FOR_OUTREACH'")
        op.execute("ALTER TYPE prospectstatus ADD VALUE 'SEND_OUTREACH_FAILED'")
    pass


def downgrade():
    op.execute("ALTER TYPE prospectstatus RENAME TO prospectstatus_old")
    op.execute("CREATE TYPE prospectstatus AS ENUM('PROSPECTED', 'NOT_QUALIFIED', 'SENT_OUTREACH', 'ACCEPTED', 'RESPONDED', 'ACTIVE_CONVO', 'SCHEDULING', 'NOT_INTERESTED', 'DEMO_SET', 'DEMO_WON', 'DEMO_LOSS')")
    op.execute((
        "ALTER TABLE prospect ALTER COLUMN status TYPE prospectstatus USING "
        "status::text::prospectstatus"
    ))

    # This needs reworking. The below code is not working.
    # op.execute((
    #     "ALTER TABLE client ALTER COLUMN notification_allowlist TYPE prospectstatus USING "
    #     "notification_allowlist::prospectstatus[]"
    # ))
    # prospect_status = sa.Enum('PROSPECTED', 'NOT_QUALIFIED', 'SENT_OUTREACH', 'ACCEPTED', 'RESPONDED', 'ACTIVE_CONVO', 'SCHEDULING', 'NOT_INTERESTED', 'DEMO_SET', 'DEMO_WON', 'DEMO_LOSS', name='prospectstatus')
    # op.alter_column("client", "notification_allowlist", type_=sa.dialects.postgresql.ARRAY(prospect_status), nullable=True)
    op.execute((
        "ALTER TABLE prospect_status_records ALTER COLUMN to_status TYPE prospectstatus USING "
        "to_status::text::prospectstatus"
    ))
    op.execute((
        "ALTER TABLE prospect_status_records ALTER COLUMN from_status TYPE prospectstatus USING "
        "from_status::text::prospectstatus"
    ))
    op.execute("DROP TYPE prospectstatus_old")
    pass
