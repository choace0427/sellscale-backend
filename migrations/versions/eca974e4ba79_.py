"""Added is_pre_onboarding_survey_imported column to client

Revision ID: eca974e4ba79
Revises: d89e740c04b2
Create Date: 2023-09-27 16:24:35.279112

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "eca974e4ba79"
down_revision = "d89e740c04b2"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client",
        sa.Column("is_pre_onboarding_survey_imported", sa.Boolean(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client", "is_pre_onboarding_survey_imported")
    # ### end Alembic commands ###
