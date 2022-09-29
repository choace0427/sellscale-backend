"""add more values to research point type

Revision ID: c331ef60533b
Revises: fb6bed62d598
Create Date: 2022-09-29 10:38:34.128697

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c331ef60533b"
down_revision = "fb6bed62d598"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")

    op.execute("ALTER TYPE researchpointtype ADD VALUE 'CURRENT_JOB_DESCRIPTION'")
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'CURRENT_JOB_SPECIALTIES'")
    op.execute(
        "ALTER TYPE researchpointtype ADD VALUE 'CURRENT_EXPERIENCE_DESCRIPTION'"
    )
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'YEARS_OF_EXPERIENCE'")
    op.execute(
        "ALTER TYPE researchpointtype ADD VALUE 'YEARS_OF_EXPERIENCE_AT_CURRENT_JOB'"
    )
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'LIST_OF_PAST_JOBS'")
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'RECENT_PATENTS'")
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'RECENT_RECOMMENDATIONS'")

    pass


def downgrade():
    pass
