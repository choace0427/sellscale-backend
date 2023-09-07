"""Added UI overlay

Revision ID: b8e1c7c9eaa6
Revises: c076c880b599
Create Date: 2023-09-06 18:10:57.598926

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e1c7c9eaa6'
down_revision = 'c076c880b599'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('browser_extension_ui_overlay', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'browser_extension_ui_overlay')
    # ### end Alembic commands ###
