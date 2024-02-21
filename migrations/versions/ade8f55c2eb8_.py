"""Added on_demo_set_webhook column to client

Revision ID: ade8f55c2eb8
Revises: 45c457cdc025
Create Date: 2024-02-18 20:22:13.879023

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ade8f55c2eb8"
down_revision = "45c457cdc025"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client", sa.Column("on_demo_set_webhook", sa.String(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client", "on_demo_set_webhook")
    # ### end Alembic commands ###