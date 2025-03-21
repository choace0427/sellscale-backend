"""Added transformer blocklists

Revision ID: a2edb0e9a599
Revises: 777c88e1d8c5
Create Date: 2023-09-13 11:38:21.260623

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2edb0e9a599'
down_revision = '777c88e1d8c5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('bump_framework', sa.Column('transformer_blocklist', sa.ARRAY(sa.Enum('CURRENT_JOB_DESCRIPTION', 'CURRENT_JOB_SPECIALTIES', 'CURRENT_EXPERIENCE_DESCRIPTION', 'LINKEDIN_BIO_SUMMARY', 'YEARS_OF_EXPERIENCE', 'YEARS_OF_EXPERIENCE_AT_CURRENT_JOB', 'LIST_OF_PAST_JOBS', 'RECENT_PATENTS', 'RECENT_RECOMMENDATIONS', 'GENERAL_WEBSITE_TRANSFORMER', 'COMMON_EDUCATION', 'SERP_NEWS_SUMMARY', 'SERP_NEWS_SUMMARY_NEGATIVE', 'CUSTOM', name='researchpointtype')), nullable=True))
    op.add_column('client_archetype', sa.Column('transformer_blocklist_initial', sa.ARRAY(sa.Enum('CURRENT_JOB_DESCRIPTION', 'CURRENT_JOB_SPECIALTIES', 'CURRENT_EXPERIENCE_DESCRIPTION', 'LINKEDIN_BIO_SUMMARY', 'YEARS_OF_EXPERIENCE', 'YEARS_OF_EXPERIENCE_AT_CURRENT_JOB', 'LIST_OF_PAST_JOBS', 'RECENT_PATENTS', 'RECENT_RECOMMENDATIONS', 'GENERAL_WEBSITE_TRANSFORMER', 'COMMON_EDUCATION', 'SERP_NEWS_SUMMARY', 'SERP_NEWS_SUMMARY_NEGATIVE', 'CUSTOM', name='researchpointtype')), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_archetype', 'transformer_blocklist_initial')
    op.drop_column('bump_framework', 'transformer_blocklist')
    # ### end Alembic commands ###
