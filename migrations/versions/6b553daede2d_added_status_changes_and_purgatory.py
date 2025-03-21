"""Added status changes and purgatory

Revision ID: 6b553daede2d
Revises: b690480f2618
Create Date: 2023-04-21 12:02:09.237335

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6b553daede2d'
down_revision = 'b690480f2618'
branch_labels = None
depends_on = None


def upgrade():

    op.execute("CREATE TYPE prospecthiddenreason AS ENUM ('RECENTLY_BUMPED', 'STATUS_CHANGE', 'MANUAL')")

    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect', sa.Column('hidden_until', sa.DateTime(), nullable=True))
    op.add_column('prospect', sa.Column('hidden_reason', sa.Enum('RECENTLY_BUMPED', 'STATUS_CHANGE', 'MANUAL', name='prospecthiddenreason'), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    pass
    op.drop_column('prospect', 'hidden_reason')
    op.drop_column('prospect', 'hidden_until')
    # ### end Alembic commands ###
