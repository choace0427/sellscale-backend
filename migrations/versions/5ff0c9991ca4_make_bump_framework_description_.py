"""Make bump framework description limitless

Revision ID: 5ff0c9991ca4
Revises: 6386c539174e
Create Date: 2023-05-08 12:11:56.230162

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ff0c9991ca4'
down_revision = '6386c539174e'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add a new column with the desired character limit
    op.add_column('bump_framework', sa.Column('new_description', sa.String(length=4000), nullable=True))

    # 2. Copy data from old column to new column
    op.execute('UPDATE bump_framework SET new_description = description')

    # 3. Drop the old column
    op.drop_column('bump_framework', 'description')

    # 4. Rename the new column to the old column name
    op.alter_column('bump_framework', 'new_description', new_column_name='description')


def downgrade():
    pass
