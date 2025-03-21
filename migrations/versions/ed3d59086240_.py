"""empty message

Revision ID: ed3d59086240
Revises: 608abe9a1293
Create Date: 2023-04-17 20:05:24.579712

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed3d59086240'
down_revision = '608abe9a1293'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_archetype', sa.Column('vessel_sequence_id', sa.String(), nullable=True))
    op.add_column('prospect_email', sa.Column('vessel_sequence_id', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect_email', 'vessel_sequence_id')
    op.drop_column('client_archetype', 'vessel_sequence_id')
    # ### end Alembic commands ###
