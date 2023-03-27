""" Add new message status values

Revision ID: ef24bd900645
Revises: 77085ada09dc
Create Date: 2023-03-27 14:57:52.336324

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef24bd900645'
down_revision = '77085ada09dc'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE generatedmessagestatus ADD VALUE 'QUEUED_FOR_OUTREACH'")
        op.execute("ALTER TYPE generatedmessagestatus ADD VALUE 'FAILED_TO_SEND'")
    pass


def downgrade():
    op.execute("ALTER TYPE generatedmessagestatus RENAME TO generatedmessagestatus_old")
    op.execute("CREATE TYPE generatedmessagestatus AS ENUM('DRAFT', 'BLOCKED', 'APPROVED', 'SENT')")
    op.execute((
        "ALTER TABLE generated_message ALTER COLUMN message_status TYPE generatedmessagestatus USING "
        "message_status::text::generatedmessagestatus"
    ))

    op.execute("DROP TYPE generatedmessagestatus_old")
    pass
