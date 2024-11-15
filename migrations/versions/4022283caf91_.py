"""Added editing_due_date to OutboundCampaign

Revision ID: 4022283caf91
Revises: 4e1feddd28a3
Create Date: 2023-01-19 12:12:32.754099

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4022283caf91"
down_revision = "4e1feddd28a3"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "outbound_campaign", sa.Column("editing_due_date", sa.DateTime(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("outbound_campaign", "editing_due_date")
    # ### end Alembic commands ###
