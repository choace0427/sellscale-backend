"""Rename hunter_email_score to email_score

Revision ID: 785137c285bb
Revises: 39eab9df99a0
Create Date: 2024-01-22 14:50:07.879283

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "785137c285bb"
down_revision = "39eab9df99a0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("prospect", "hunter_email_score", new_column_name="email_score")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("prospect", "email_score", new_column_name="hunter_email_score")
    # ### end Alembic commands ###
