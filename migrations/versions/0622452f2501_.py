""" Add failed_outreach_error to generated_message

Revision ID: 0622452f2501
Revises: ef24bd900645
Create Date: 2023-03-27 15:44:59.392780

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0622452f2501'
down_revision = 'ef24bd900645'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('generated_message', sa.Column('failed_outreach_error', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('generated_message', 'failed_outreach_error')
    # ### end Alembic commands ###
