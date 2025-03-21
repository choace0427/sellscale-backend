"""Add Default Transformer Blocklist to SDR

Revision ID: 70aa9e2a6c87
Revises: 55a524e88e5d
Create Date: 2024-03-11 11:08:05.039861

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "70aa9e2a6c87"
down_revision = "55a524e88e5d"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_sdr",
        sa.Column(
            "default_transformer_blocklist", sa.ARRAY(sa.String()), nullable=True
        ),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client_sdr", "default_transformer_blocklist")
    # ### end Alembic commands ###
