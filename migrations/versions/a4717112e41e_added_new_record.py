"""Added new record

Revision ID: a4717112e41e
Revises: f7c166990461
Create Date: 2024-02-20 23:43:55.855033

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4717112e41e'
down_revision = 'f7c166990461'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_sync_crm', sa.Column('event_handlers', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_sync_crm', 'event_handlers')
    # ### end Alembic commands ###
