"""Add li_health fields

Revision ID: 9dac423385df
Revises: 1e557f298a07
Create Date: 2023-09-13 16:17:14.611591

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9dac423385df'
down_revision = '1e557f298a07'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('li_health_good_title', sa.Boolean(), nullable=True))
    op.add_column('client_sdr', sa.Column('li_health_cover_image', sa.Boolean(), nullable=True))
    op.add_column('client_sdr', sa.Column('li_health_profile_photo', sa.Boolean(), nullable=True))
    op.add_column('client_sdr', sa.Column('li_health_premium', sa.Boolean(), nullable=True))
    op.drop_column('client_sdr', 'li_premium')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('li_premium', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.drop_column('client_sdr', 'li_health_premium')
    op.drop_column('client_sdr', 'li_health_profile_photo')
    op.drop_column('client_sdr', 'li_health_cover_image')
    op.drop_column('client_sdr', 'li_health_good_title')
    # ### end Alembic commands ###
