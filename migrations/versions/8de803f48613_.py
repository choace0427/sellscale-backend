"""Added step_number column to client_assets

Revision ID: 8de803f48613
Revises: 08a0214c1ede
Create Date: 2024-03-08 15:33:44.497312

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8de803f48613"
down_revision = "08a0214c1ede"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_assets", sa.Column("step_number", sa.Integer(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client_assets", "step_number")
    # ### end Alembic commands ###
