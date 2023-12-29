"""Added disqualification reason and blocks

Revision ID: 1af370173391
Revises: 451335bdb94a
Create Date: 2023-12-28 14:41:44.613636

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1af370173391"
down_revision = "451335bdb94a"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "prospect", sa.Column("disqualification_reason", sa.String(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "disqualification_reason")
    # ### end Alembic commands ###