"""Added option_filters

Revision ID: d43e48fa540a
Revises: d6665ef816e9
Create Date: 2023-08-07 16:51:50.513731

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd43e48fa540a'
down_revision = 'd6665ef816e9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_archetype', sa.Column('icp_matching_option_filters', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_archetype', 'icp_matching_option_filters')
    # ### end Alembic commands ###
