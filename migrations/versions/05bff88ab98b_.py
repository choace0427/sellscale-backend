"""Added included/excluded individual seniority keywords to icp_scoring_ruleset

Revision ID: 05bff88ab98b
Revises: 0b41a1a83941
Create Date: 2024-01-04 10:38:20.986579

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "05bff88ab98b"
down_revision = "0b41a1a83941"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "icp_scoring_ruleset",
        sa.Column(
            "included_individual_seniority_keywords",
            sa.ARRAY(sa.String()),
            nullable=True,
        ),
    )
    op.add_column(
        "icp_scoring_ruleset",
        sa.Column(
            "excluded_individual_seniority_keywords",
            sa.ARRAY(sa.String()),
            nullable=True,
        ),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("icp_scoring_ruleset", "excluded_individual_seniority_keywords")
    op.drop_column("icp_scoring_ruleset", "included_individual_seniority_keywords")
    # ### end Alembic commands ###
