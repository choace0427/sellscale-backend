"""Generated_message research points is nullable now

Revision ID: 58c18691db53
Revises: 03475934fa5c
Create Date: 2023-08-25 09:47:29.729057

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '58c18691db53'
down_revision = '03475934fa5c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('generated_message', 'research_points',
               existing_type=postgresql.ARRAY(sa.INTEGER()),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('generated_message', 'research_points',
               existing_type=postgresql.ARRAY(sa.INTEGER()),
               nullable=False)
    # ### end Alembic commands ###