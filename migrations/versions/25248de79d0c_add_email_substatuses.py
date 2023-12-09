"""Add email substatuses

Revision ID: 25248de79d0c
Revises: ff2743a4ebf5
Create Date: 2023-12-08 16:43:29.730769

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "25248de79d0c"
down_revision = "ff2743a4ebf5"
branch_labels = None
depends_on = None


def upgrade():
    ACTIVE_CONVO_QUESTION = "ACTIVE_CONVO_QUESTION"
    ACTIVE_CONVO_QUAL_NEEDED = "ACTIVE_CONVO_QUAL_NEEDED"
    ACTIVE_CONVO_OBJECTION = "ACTIVE_CONVO_OBJECTION"
    ACTIVE_CONVO_SCHEDULING = "ACTIVE_CONVO_SCHEDULING"
    ACTIVE_CONVO_NEXT_STEPS = "ACTIVE_CONVO_NEXT_STEPS"
    ACTIVE_CONVO_REVIVAL = "ACTIVE_CONVO_REVIVAL"
    ACTIVE_CONVO_OOO = "ACTIVE_CONVO_OOO"
    ACTIVE_CONVO_REFERRAL = "ACTIVE_CONVO_REFERRAL"
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute(
        "ALTER TYPE prospectemailoutreachstatus ADD VALUE IF NOT EXISTS 'ACTIVE_CONVO_QUESTION';"
    )
    op.execute(
        "ALTER TYPE prospectemailoutreachstatus ADD VALUE IF NOT EXISTS 'ACTIVE_CONVO_QUAL_NEEDED';"
    )
    op.execute(
        "ALTER TYPE prospectemailoutreachstatus ADD VALUE IF NOT EXISTS 'ACTIVE_CONVO_OBJECTION';"
    )
    op.execute(
        "ALTER TYPE prospectemailoutreachstatus ADD VALUE IF NOT EXISTS 'ACTIVE_CONVO_SCHEDULING';"
    )
    op.execute(
        "ALTER TYPE prospectemailoutreachstatus ADD VALUE IF NOT EXISTS 'ACTIVE_CONVO_NEXT_STEPS';"
    )
    op.execute(
        "ALTER TYPE prospectemailoutreachstatus ADD VALUE IF NOT EXISTS 'ACTIVE_CONVO_REVIVAL';"
    )
    op.execute(
        "ALTER TYPE prospectemailoutreachstatus ADD VALUE IF NOT EXISTS 'ACTIVE_CONVO_OOO';"
    )
    op.execute(
        "ALTER TYPE prospectemailoutreachstatus ADD VALUE IF NOT EXISTS 'ACTIVE_CONVO_REFERRAL';"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
