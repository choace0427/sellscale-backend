"""Add transformer blocklist to email sequence steps

Revision ID: 0d95df4ea69d
Revises: cd893a132812
Create Date: 2023-11-06 11:02:49.926615

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d95df4ea69d'
down_revision = 'cd893a132812'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('email_sequence_step', sa.Column('transformer_blocklist', sa.ARRAY(sa.Enum('CURRENT_JOB_DESCRIPTION', 'CURRENT_JOB_SPECIALTIES', 'CURRENT_JOB_INDUSTRY', 'CURRENT_EXPERIENCE_DESCRIPTION', 'LINKEDIN_BIO_SUMMARY', 'YEARS_OF_EXPERIENCE', 'YEARS_OF_EXPERIENCE_AT_CURRENT_JOB', 'LIST_OF_PAST_JOBS', 'RECENT_PATENTS', 'RECENT_RECOMMENDATIONS', 'GENERAL_WEBSITE_TRANSFORMER', 'COMMON_EDUCATION', 'SERP_NEWS_SUMMARY', 'SERP_NEWS_SUMMARY_NEGATIVE', 'CUSTOM', name='researchpointtype')), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('email_sequence_step', 'transformer_blocklist')
    # ### end Alembic commands ###
