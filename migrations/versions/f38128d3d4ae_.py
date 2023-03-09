""" Add SDR_QUESTIONNAIRE to researchtype

Revision ID: f38128d3d4ae
Revises: 4cd0cf89ab71
Create Date: 2023-03-09 13:53:08.601699

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f38128d3d4ae'
down_revision = '4cd0cf89ab71'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
       op.execute("ALTER TYPE researchtype ADD VALUE 'SDR_QUESTIONNAIRE'")
    pass


def downgrade():
    op.execute("ALTER TYPE researchtype RENAME TO researchtype_old")
    op.execute("CREATE TYPE researchtype AS ENUM('LINKEDIN_ISCRAPER', 'SERP_PAYLOAD')")
    op.execute((
        "ALTER TABLE research_payload ALTER COLUMN research_type TYPE researchtype USING "
        "research_type::text::researchtype"
    ))
    op.execute("DROP TYPE researchtype_old")
    pass
