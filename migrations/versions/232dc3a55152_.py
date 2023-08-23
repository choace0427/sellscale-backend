"""Added ICPScoringRuleset

Revision ID: 232dc3a55152
Revises: 1d6d05688a47
Create Date: 2023-08-23 11:15:21.654934

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "232dc3a55152"
down_revision = "1d6d05688a47"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "icp_scoring_ruleset",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("client_archetype_id", sa.Integer(), nullable=False),
        sa.Column(
            "included_individual_title_keywords", sa.ARRAY(sa.String()), nullable=False
        ),
        sa.Column(
            "excluded_individual_title_keywords", sa.ARRAY(sa.String()), nullable=False
        ),
        sa.Column(
            "included_individual_industry_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "excluded_individual_industry_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column("individual_years_of_experience_start", sa.Integer(), nullable=False),
        sa.Column("individual_years_of_experience_end", sa.Integer(), nullable=False),
        sa.Column(
            "included_individual_skills_keywords", sa.ARRAY(sa.String()), nullable=False
        ),
        sa.Column(
            "excluded_individual_skills_keywords", sa.ARRAY(sa.String()), nullable=False
        ),
        sa.Column(
            "included_individual_locations_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "excluded_individual_locations_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "included_individual_generalized_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "excluded_individual_generalized_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "included_company_name_keywords", sa.ARRAY(sa.String()), nullable=False
        ),
        sa.Column(
            "excluded_company_name_keywords", sa.ARRAY(sa.String()), nullable=False
        ),
        sa.Column(
            "included_company_locations_keywords", sa.ARRAY(sa.String()), nullable=False
        ),
        sa.Column(
            "excluded_company_locations_keywords", sa.ARRAY(sa.String()), nullable=False
        ),
        sa.Column("company_size_start", sa.Integer(), nullable=False),
        sa.Column("company_size_end", sa.Integer(), nullable=False),
        sa.Column(
            "included_company_industries_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "excluded_company_industries_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "included_company_generalized_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "excluded_company_generalized_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["client_archetype_id"],
            ["client_archetype.id"],
        ),
        sa.PrimaryKeyConstraint("client_archetype_id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("icp_scoring_ruleset")
    # ### end Alembic commands ###