"""Add fail_reason and FAIL to ProcessQueue

Revision ID: 7aeb6dbbe5e9
Revises: 620b94fc9d7b
Create Date: 2023-12-29 11:56:40.948487

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7aeb6dbbe5e9"
down_revision = "620b94fc9d7b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("process_queue", sa.Column("fail_reason", sa.String(), nullable=True))
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE processqueuestatus ADD VALUE 'FAILED'")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("process_queue", "fail_reason")
    # ### end Alembic commands ###
