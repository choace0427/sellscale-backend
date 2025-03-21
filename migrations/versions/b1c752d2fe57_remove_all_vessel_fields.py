"""Remove all vessel fields

Revision ID: b1c752d2fe57
Revises: b1f460547e34
Create Date: 2023-09-07 12:06:32.344675

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c752d2fe57'
down_revision = 'b1f460547e34'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client', 'vessel_sales_engagement_connection_id')
    op.drop_column('client', 'vessel_personalization_field_name')
    op.drop_column('client', 'vessel_crm_access_token')
    op.drop_column('client', 'vessel_access_token')
    op.drop_column('client_sdr', 'vessel_mailbox')
    op.drop_column('prospect_email', 'vessel_sequence_id')
    op.drop_column('prospect_email', 'vessel_sequence_payload_str')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect_email', sa.Column('vessel_sequence_payload_str', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('prospect_email', sa.Column('vessel_sequence_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('client_sdr', sa.Column('vessel_mailbox', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('client', sa.Column('vessel_access_token', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('client', sa.Column('vessel_crm_access_token', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('client', sa.Column('vessel_personalization_field_name', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('client', sa.Column('vessel_sales_engagement_connection_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
