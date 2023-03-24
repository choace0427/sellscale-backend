"""Added hunter_email_score to prospect

Revision ID: df1674d1839a
Revises: 5d5142d9ae9a
Create Date: 2023-03-23 18:49:28.910547

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "df1674d1839a"
down_revision = "5d5142d9ae9a"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "prospect", sa.Column("hunter_email_score", sa.Float(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "hunter_email_score")
    # ### end Alembic commands ###
