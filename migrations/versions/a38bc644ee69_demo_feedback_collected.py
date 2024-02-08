"""demo_feedback_collected

Revision ID: a38bc644ee69
Revises: df0c3ca8de30
Create Date: 2024-02-07 22:51:38.514258

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a38bc644ee69"
down_revision = "df0c3ca8de30"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("ALTER TYPE slacknotificationtype ADD VALUE 'DEMO_FEEDBACK_COLLECTED'")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("ALTER TYPE slacknotificationtype DROP VALUE 'DEMO_FEEDBACK_COLLECTED'")

    # ### end Alembic commands ###
