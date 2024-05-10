"""Remove view_email and view_linkedin columns from client_archetype

Revision ID: f808b354a028
Revises: 9b33641e8c45
Create Date: 2024-05-10 11:20:20.105589

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f808b354a028'
down_revision = '9b33641e8c45'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('client_archetype', 'view_email')
    op.drop_column('client_archetype', 'view_linkedin')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('client_archetype', sa.Column('view_linkedin', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.add_column('client_archetype', sa.Column('view_email', sa.BOOLEAN(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
