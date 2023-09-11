"""Added is_lookalike_profile column to prospect

Revision ID: 66583d7c710d
Revises: 59f726d00412
Create Date: 2023-08-30 17:40:43.441062

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "66583d7c710d"
down_revision = "59f726d00412"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "prospect", sa.Column("is_lookalike_profile", sa.Boolean(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "is_lookalike_profile")
    # ### end Alembic commands ###