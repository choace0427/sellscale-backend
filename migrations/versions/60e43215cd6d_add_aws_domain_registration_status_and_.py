"""Add aws_domain_registration status and job_id to Domain

Revision ID: 60e43215cd6d
Revises: ff85a90f2733
Create Date: 2024-01-05 15:46:51.787334

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "60e43215cd6d"
down_revision = "ff85a90f2733"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "domain",
        sa.Column("aws_domain_registration_status", sa.String(), nullable=True),
    )
    op.add_column(
        "domain",
        sa.Column("aws_domain_registration_job_id", sa.String(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("domain", "aws_domain_registration_job_id")
    op.drop_column("domain", "aws_domain_registration_status")
    # ### end Alembic commands ###
