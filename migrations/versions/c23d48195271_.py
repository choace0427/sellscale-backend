"""add citations to ai researcher answer table

Revision ID: c23d48195271
Revises: 9406464bf9d8
Create Date: 2024-07-15 14:31:22.029730

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c23d48195271'
down_revision = '9406464bf9d8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ai_researcher_answer', sa.Column('citations', sa.ARRAY(sa.String()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ai_researcher_answer', 'citations')
    # ### end Alembic commands ###