"""Added images to SDRs and prospects

Revision ID: 84b15ed16086
Revises: 91ba89e68f6d
Create Date: 2023-04-06 14:01:06.827636

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '84b15ed16086'
down_revision = '91ba89e68f6d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('img_url', sa.String(), nullable=True))
    op.add_column('client_sdr', sa.Column('img_expire', sa.Numeric(precision=20, scale=0), server_default='0', nullable=False))
    op.add_column('prospect', sa.Column('img_url', sa.String(), nullable=True))
    op.add_column('prospect', sa.Column('img_expire', sa.Numeric(precision=20, scale=0), server_default='0', nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect', 'img_expire')
    op.drop_column('prospect', 'img_url')
    op.drop_column('client_sdr', 'img_expire')
    op.drop_column('client_sdr', 'img_url')
    # ### end Alembic commands ###
