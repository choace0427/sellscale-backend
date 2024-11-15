"""Add setup_mailboxes_sdr_id on DomainSetupTracker

Revision ID: 563b223fe2c9
Revises: ea2bc5c817d0
Create Date: 2024-05-14 12:05:51.444192

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "563b223fe2c9"
down_revision = "ea2bc5c817d0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "domain_setup_tracker",
        sa.Column("setup_mailboxes_sdr_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        None, "domain_setup_tracker", "client_sdr", ["setup_mailboxes_sdr_id"], ["id"]
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "domain_setup_tracker", type_="foreignkey")
    op.drop_column("domain_setup_tracker", "setup_mailboxes_sdr_id")
    # ### end Alembic commands ###
