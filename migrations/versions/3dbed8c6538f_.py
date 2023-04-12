""" Add intent score columns to prospect table

Revision ID: 3dbed8c6538f
Revises: 5aaf85ee8fa7
Create Date: 2023-04-08 11:13:39.675468

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3dbed8c6538f"
down_revision = "a1d23e5869fd"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("prospect", sa.Column("li_intent_score", sa.Float(), nullable=True))
    op.add_column(
        "prospect", sa.Column("email_intent_score", sa.Float(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "email_intent_score")
    op.drop_column("prospect", "li_intent_score")
    # ### end Alembic commands ###
