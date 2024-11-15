"""Added verified and website_base columns to track_source

Revision ID: 26da319a7962
Revises: 36ca895f6903
Create Date: 2024-06-27 09:45:27.181305

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26da319a7962'
down_revision = '36ca895f6903'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('track_source', sa.Column('verified', sa.Boolean(), nullable=True))
    op.add_column('track_source', sa.Column('website_base', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('track_source', 'website_base')
    op.drop_column('track_source', 'verified')
    # ### end Alembic commands ###
