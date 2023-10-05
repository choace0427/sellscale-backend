"""Updated default bump amt

Revision ID: 39325fc7f92c
Revises: 9a64d44e988b
Create Date: 2023-10-02 16:17:15.683947

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39325fc7f92c'
down_revision = '9a64d44e988b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('client_archetype', 'li_bump_amount',
               existing_type=sa.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('client_archetype', 'li_bump_amount',
               existing_type=sa.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###