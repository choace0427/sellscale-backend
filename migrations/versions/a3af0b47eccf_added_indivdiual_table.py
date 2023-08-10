"""Added indivdiual table

Revision ID: a3af0b47eccf
Revises: d43e48fa540a
Create Date: 2023-08-08 18:38:21.688660

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a3af0b47eccf"
down_revision = "d43e48fa540a"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "individual",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("bio", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("instagram_url", sa.String(), nullable=True),
        sa.Column("facebook_url", sa.String(), nullable=True),
        sa.Column("twitter_url", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("li_urn_id", sa.String(), nullable=True),
        sa.Column("img_url", sa.String(), nullable=True),
        sa.Column("img_expire", sa.Numeric(precision=20, scale=0), nullable=False),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("company_url", sa.String(), nullable=True),
        sa.Column("company_size", sa.String(), nullable=True),
        sa.Column("company_description", sa.String(), nullable=True),
        sa.Column("linkedin_followers", sa.Integer(), nullable=True),
        sa.Column("instagram_followers", sa.Integer(), nullable=True),
        sa.Column("facebook_followers", sa.Integer(), nullable=True),
        sa.Column("twitter_followers", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("linkedin_url"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("individual")
    # ### end Alembic commands ###