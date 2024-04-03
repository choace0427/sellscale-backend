"""Remove ProspectUploadBatch

Revision ID: 1267ca93fd10
Revises: 10e435da39b7
Create Date: 2024-04-03 12:54:29.915495

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "1267ca93fd10"
down_revision = "10e435da39b7"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("prospect_upload_batch")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "prospect_upload_batch",
        sa.Column(
            "created_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True
        ),
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("archetype_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("batch_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("num_prospects", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["archetype_id"],
            ["client_archetype.id"],
            name="prospect_upload_batch_archetype_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="prospect_upload_batch_pkey"),
    )
    # ### end Alembic commands ###