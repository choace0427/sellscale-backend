"""Add aws_amplify_app_id into Domain

Revision ID: bbdd2f344aab
Revises: 05bff88ab98b
Create Date: 2024-01-05 10:46:06.096958

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bbdd2f344aab"
down_revision = "05bff88ab98b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("domain", sa.Column("aws_amplify_app_id", sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("domain", "aws_amplify_app_id")
    # ### end Alembic commands ###
