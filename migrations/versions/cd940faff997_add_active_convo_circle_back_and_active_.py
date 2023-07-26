"""Add ACTIVE_CONVO_CIRCLE_BACK and ACTIVE_CONVO_REFERRAL

Revision ID: cd940faff997
Revises: 801b4615bbed
Create Date: 2023-07-25 16:13:58.019885

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cd940faff997'
down_revision = '801b4615bbed'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE prospectstatus ADD VALUE 'ACTIVE_CONVO_CIRCLE_BACK'")
        op.execute("ALTER TYPE prospectstatus ADD VALUE 'ACTIVE_CONVO_REFERRAL'")
    pass


def downgrade():
    op.execute("ALTER TYPE prospectstatus RENAME TO prospectstatus_old")
    op.execute("CREATE TYPE prospectstatus AS ENUM('PROSPECTED', 'NOT_QUALIFIED', 'QUEUED_FOR_OUTREACH', 'SEND_OUTREACH_FAILED', 'SENT_OUTREACH', 'ACCEPTED', 'RESPONDED', 'ACTIVE_CONVO', 'SCHEDULING', 'NOT_INTERESTED', 'DEMO_SET', 'DEMO_WON', 'DEMO_LOSS', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_QUAL_NEEDED', 'ACTIVE_CONVO_OBJECTION', 'ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_REVIVAL')")
    op.execute((
        "ALTER TABLE prospect ALTER COLUMN status TYPE prospectstatus USING "
        "status::text::prospectstatus"
    ))
    op.execute((
        "ALTER TABLE prospect_status_records ALTER COLUMN from_status TYPE prospectstatus USING "
        "from_status::text::prospectstatus"
    ))
    op.execute((
        "ALTER TABLE prospect_status_records ALTER COLUMN to_status TYPE prospectstatus USING "
        "to_status::text::prospectstatus"
    ))


    op.execute("DROP TYPE prospectstatus_old")
    pass
