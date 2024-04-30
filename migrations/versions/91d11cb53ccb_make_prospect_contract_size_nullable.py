"""Make prospect.contract_size nullable

Revision ID: 91d11cb53ccb
Revises: 6c37f834594c
Create Date: 2024-04-30 10:29:48.172788

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "91d11cb53ccb"
down_revision = "6c37f834594c"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "prospect",
        "contract_size",
        existing_type=sa.INTEGER(),
        nullable=True,
        server_default=None,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "prospect",
        "contract_size",
        existing_type=sa.INTEGER(),
        nullable=False,
        server_default=sa.text("10000"),
    )
    # ### end Alembic commands ###
