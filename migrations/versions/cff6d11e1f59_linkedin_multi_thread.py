"""linkedin_multi_thread

Revision ID: cff6d11e1f59
Revises: d0078c566e05
Create Date: 2024-02-14 04:56:48.226578

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cff6d11e1f59"
down_revision = "d79233898e5a"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("ALTER TYPE slacknotificationtype ADD VALUE 'LINKEDIN_MULTI_THREAD'")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("ALTER TYPE slacknotificationtype DROP VALUE 'LINKEDIN_MULTI_THREAD'")

    # ### end Alembic commands ###
