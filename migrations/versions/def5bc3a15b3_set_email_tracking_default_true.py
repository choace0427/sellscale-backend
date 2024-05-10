"""set email tracking default true

Revision ID: def5bc3a15b3
Revises: 284fc588d751
Create Date: 2024-05-10 13:53:55.927907

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'def5bc3a15b3'
down_revision = 'f808b354a028'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('client_archetype', 'email_open_tracking_enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.true())
    op.alter_column('client_archetype', 'email_link_tracking_enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.true())
    op.alter_column('client_sdr', 'email_open_tracking_enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.true())
    op.alter_column('client_sdr', 'email_link_tracking_enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.true())

def downgrade():
    op.alter_column('client_archetype', 'email_open_tracking_enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.false())
    op.alter_column('client_archetype', 'email_link_tracking_enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.false())
    op.alter_column('client_sdr', 'email_open_tracking_enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.false())
    op.alter_column('client_sdr', 'email_link_tracking_enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.false())