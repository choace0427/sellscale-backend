"""Added max pages

Revision ID: 1a6f6cb57caf
Revises: b3527d5468e7
Create Date: 2024-03-20 17:06:14.709813

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1a6f6cb57caf'
down_revision = 'b3527d5468e7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('apollo_scraper_job', sa.Column('max_pages', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('apollo_scraper_job', 'max_pages')
    # ### end Alembic commands ###
