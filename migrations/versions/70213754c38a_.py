"""Added do not contact fields

Revision ID: 70213754c38a
Revises: 4b278a47ff33
Create Date: 2023-11-13 13:23:27.395492

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '70213754c38a'
down_revision = '4b278a47ff33'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client', sa.Column('do_not_contact_prospect_location_keywords', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('client_sdr', sa.Column('do_not_contact_prospect_location_keywords', sa.ARRAY(sa.String()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'do_not_contact_prospect_location_keywords')
    op.drop_column('client', 'do_not_contact_prospect_location_keywords')
    # ### end Alembic commands ###
