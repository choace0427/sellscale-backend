""" Add entry_processed column to linkedin_conversation_entry

Revision ID: 560ecd9e8a0a
Revises: f29ccf5d7d96
Create Date: 2023-02-22 17:38:14.676072

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '560ecd9e8a0a'
down_revision = 'f29ccf5d7d96'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('linkedin_conversation_entry', sa.Column('entry_processed', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('linkedin_conversation_entry', 'entry_processed')
    # ### end Alembic commands ###
