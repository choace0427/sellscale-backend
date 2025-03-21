"""Added do not contact to SDR

Revision ID: 42ba2c83049d
Revises: 6897a968220b
Create Date: 2023-08-29 14:29:28.776032

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '42ba2c83049d'
down_revision = '6897a968220b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sdr', sa.Column('do_not_contact_keywords_in_company_names', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('client_sdr', sa.Column('do_not_contact_company_names', sa.ARRAY(sa.String()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sdr', 'do_not_contact_company_names')
    op.drop_column('client_sdr', 'do_not_contact_keywords_in_company_names')
    # ### end Alembic commands ###
