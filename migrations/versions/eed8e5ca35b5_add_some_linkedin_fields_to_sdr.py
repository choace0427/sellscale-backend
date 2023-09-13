"""Add some linkedin fields to SDR

Revision ID: eed8e5ca35b5
Revises: a2edb0e9a599
Create Date: 2023-09-13 15:30:15.308011

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eed8e5ca35b5'
down_revision = 'a2edb0e9a599'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('linkedin_url', sa.String(), nullable=True))
    op.add_column('client_sdr', sa.Column('li_health', sa.Float(), nullable=True))
    op.add_column('client_sdr', sa.Column('li_cover_img_url', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'li_cover_img_url')
    op.drop_column('client_sdr', 'li_health')
    op.drop_column('client_sdr', 'linkedin_url')
    # ### end Alembic commands ###
