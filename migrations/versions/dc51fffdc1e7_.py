"""added active field to archetypes

Revision ID: dc51fffdc1e7
Revises: 02021a398f32
Create Date: 2022-11-23 16:04:57.865253

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "dc51fffdc1e7"
down_revision = "02021a398f32"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("client_archetype", sa.Column("active", sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client_archetype", "active")
    # ### end Alembic commands ###
