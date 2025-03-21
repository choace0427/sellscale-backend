"""Added included/excluded keywords to ruleset

Revision ID: 4ef624a3354d
Revises: 9f254c0afb1f
Create Date: 2023-12-04 14:59:12.865009

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4ef624a3354d"
down_revision = "9f254c0afb1f"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "icp_scoring_ruleset",
        sa.Column(
            "included_individual_education_keywords",
            sa.ARRAY(sa.String()),
            nullable=True,
        ),
    )
    op.drop_column("icp_scoring_ruleset", "included_individual_educatio_keywords")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "icp_scoring_ruleset",
        sa.Column(
            "included_individual_educatio_keywords",
            postgresql.ARRAY(sa.VARCHAR()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_column("icp_scoring_ruleset", "included_individual_education_keywords")
    # ### end Alembic commands ###
