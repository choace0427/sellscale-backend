"""Switched enums to strings

Revision ID: e17a8c574b86
Revises: 6c9a26d736df
Create Date: 2024-01-31 20:05:43.596379

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e17a8c574b86"
down_revision = "6c9a26d736df"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "bump_framework",
        "transformer_blocklist",
        type_=sa.ARRAY(sa.String()),
    )

    op.alter_column(
        "client_archetype",
        "transformer_blocklist",
        type_=sa.ARRAY(sa.String()),
    )

    op.alter_column(
        "client_archetype",
        "transformer_blocklist_initial",
        type_=sa.ARRAY(sa.String()),
    )

    op.alter_column(
        "email_reply_framework",
        "research_blocklist",
        type_=sa.ARRAY(sa.String()),
    )

    op.alter_column(
        "email_sequence_step",
        "transformer_blocklist",
        type_=sa.ARRAY(sa.String()),
    )

    op.alter_column(
        "email_template_pool",
        "transformer_blocklist",
        type_=sa.ARRAY(sa.String()),
    )

    op.alter_column(
        "linkedin_initial_message_template_library",
        "transformer_blocklist",
        type_=sa.ARRAY(sa.String()),
    )

    op.alter_column(
        "bump_framework_templates",
        "transformer_blocklist",
        type_=sa.ARRAY(sa.String()),
    )

    op.alter_column(
        "research_point",
        "research_point_type",
        type_=sa.String(),
    )


def downgrade():
    pass
