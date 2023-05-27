"""Added email additional column

Revision ID: 5bd145039bf2
Revises: aa688f9d5655
Create Date: 2023-05-26 17:25:40.016442

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5bd145039bf2'
down_revision = 'aa688f9d5655'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('prospect', sa.Column('email_additional', sa.ARRAY(sa.JSON()), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect', 'email_additional')
    # ### end Alembic commands ###
