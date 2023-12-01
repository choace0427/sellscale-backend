"""Added colloquialized title to prospect

Revision ID: 5fca5c77e7e7
Revises: ef43f9c9c6c4
Create Date: 2023-11-21 17:11:10.431834

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5fca5c77e7e7"
down_revision = "ef43f9c9c6c4"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "prospect", sa.Column("colloquialized_title", sa.String(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "colloquialized_title")
    # ### end Alembic commands ###