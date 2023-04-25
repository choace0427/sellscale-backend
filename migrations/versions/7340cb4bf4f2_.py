"""Added is_unassigned_contact_archetype to client_archetype

Revision ID: 7340cb4bf4f2
Revises: 33039437d263
Create Date: 2023-04-25 10:53:37.005784

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7340cb4bf4f2"
down_revision = "33039437d263"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client_archetype",
        sa.Column("is_unassigned_contact_archetype", sa.Boolean(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("client_archetype", "is_unassigned_contact_archetype")
    # ### end Alembic commands ###
