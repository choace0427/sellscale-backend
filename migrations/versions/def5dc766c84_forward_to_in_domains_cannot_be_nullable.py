"""forward_to in Domains cannot be nullable

Revision ID: def5dc766c84
Revises: 385cc0fbc605
Create Date: 2023-12-27 12:16:22.757994

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "def5dc766c84"
down_revision = "385cc0fbc605"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "domain", "forward_to", existing_type=sa.VARCHAR(length=255), nullable=False
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "domain", "forward_to", existing_type=sa.VARCHAR(length=255), nullable=True
    )
    # ### end Alembic commands ###
