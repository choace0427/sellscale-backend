"""Add Email OOO Notification

Revision ID: 677d212bac54
Revises: e1d78169ccfc
Create Date: 2024-06-19 11:51:19.745468

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "677d212bac54"
down_revision = "e1d78169ccfc"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("ALTER TYPE slacknotificationtype ADD VALUE 'EMAIL_OOO'")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("ALTER TYPE slacknotificationtype DROP VALUE 'EMAIL_OOO'")

    # ### end Alembic commands ###
