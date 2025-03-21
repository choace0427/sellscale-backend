"""Add Campaign Completed Notification

Revision ID: de87abe4bbcf
Revises: 818638d933ca
Create Date: 2024-04-02 11:03:32.199415

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "de87abe4bbcf"
down_revision = "818638d933ca"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("ALTER TYPE slacknotificationtype ADD VALUE 'CAMPAIGN_COMPLETED'")

    # ### end Alembic commands ###
    pass


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("ALTER TYPE slacknotificationtype DROP VALUE 'CAMPAIGN_COMPLETED'")

    # ### end Alembic commands ###
    pass
