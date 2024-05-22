"""Added is_ai_research_personalization_enabled column to client_archetype

Revision ID: 1d19c3a456fd
Revises: a1d1ef0698e0
Create Date: 2024-05-22 12:46:26.053625

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1d19c3a456fd'
down_revision = 'a1d1ef0698e0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_archetype', sa.Column('is_ai_research_personalization_enabled', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_archetype', 'is_ai_research_personalization_enabled')
    # ### end Alembic commands ###
