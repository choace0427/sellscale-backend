"""linkedin_connection_connected.py

Revision ID: ab087e6933d2
Revises: e89842acea95
Create Date: 2024-02-14 04:50:45.141152

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ab087e6933d2"
down_revision = "837457e56296"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute(
        "ALTER TYPE slacknotificationtype ADD VALUE 'LINKEDIN_CONNECTION_CONNECTED'"
    )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute(
        "ALTER TYPE slacknotificationtype DROP VALUE 'LINKEDIN_CONNECTION_CONNECTED'"
    )

    # ### end Alembic commands ###