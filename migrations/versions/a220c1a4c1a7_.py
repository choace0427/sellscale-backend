"""Make email_replies blacklist a list of ResearchPointType

Revision ID: a220c1a4c1a7
Revises: 3478a7fcd78d
Create Date: 2024-01-10 12:58:03.754318

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a220c1a4c1a7"
down_revision = "3478a7fcd78d"
branch_labels = None
depends_on = None


def upgrade():
    # Drop email_reply_framework.research_blocklist
    op.drop_column("email_reply_framework", "research_blocklist")

    # Add it back as a list of ResearchPointType
    op.add_column(
        "email_reply_framework",
        sa.Column(
            "research_blocklist",
            sa.ARRAY(
                postgresql.ENUM(
                    "CURRENT_JOB_DESCRIPTION",
                    "CURRENT_JOB_SPECIALTIES",
                    "CURRENT_JOB_INDUSTRY",
                    "CURRENT_EXPERIENCE_DESCRIPTION",
                    "LINKEDIN_BIO_SUMMARY",
                    "YEARS_OF_EXPERIENCE",
                    "YEARS_OF_EXPERIENCE_AT_CURRENT_JOB",
                    "LIST_OF_PAST_JOBS",
                    "RECENT_PATENTS",
                    "RECENT_RECOMMENDATIONS",
                    "GENERAL_WEBSITE_TRANSFORMER",
                    "COMMON_EDUCATION",
                    "SERP_NEWS_SUMMARY",
                    "SERP_NEWS_SUMMARY_NEGATIVE",
                    "CUSTOM",
                    name="researchpointtype",
                    create_type=False,
                ),
            ),
            nullable=True,
        ),
    )
    pass


def downgrade():
    # Drop email_reply_framework.research_blocklist
    op.drop_column("email_reply_framework", "research_blocklist")

    # Add it back as a list of ResearchPointType
    op.add_column(
        "email_reply_framework",
        sa.Column(
            "research_blocklist",
            postgresql.ENUM(
                "CURRENT_JOB_DESCRIPTION",
                "CURRENT_JOB_SPECIALTIES",
                "CURRENT_JOB_INDUSTRY",
                "CURRENT_EXPERIENCE_DESCRIPTION",
                "LINKEDIN_BIO_SUMMARY",
                "YEARS_OF_EXPERIENCE",
                "YEARS_OF_EXPERIENCE_AT_CURRENT_JOB",
                "LIST_OF_PAST_JOBS",
                "RECENT_PATENTS",
                "RECENT_RECOMMENDATIONS",
                "GENERAL_WEBSITE_TRANSFORMER",
                "COMMON_EDUCATION",
                "SERP_NEWS_SUMMARY",
                "SERP_NEWS_SUMMARY_NEGATIVE",
                "CUSTOM",
                name="researchpointtype",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    pass
