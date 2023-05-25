""" Add substatus to bump_framework

Revision ID: e51c943d4e4e
Revises: 66f70560de37
Create Date: 2023-05-25 12:45:55.921197

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e51c943d4e4e'
down_revision = '66f70560de37'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('bump_framework', sa.Column('substatus', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('bump_framework', 'substatus')
    # ### end Alembic commands ###
