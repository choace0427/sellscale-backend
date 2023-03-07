"""Added vessel_crm_id and vessel_crm_access_token to prospect and client 

Revision ID: 79cebdbb8459
Revises: 35af94f00826
Create Date: 2023-03-07 13:26:10.809184

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "79cebdbb8459"
down_revision = "35af94f00826"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "client", sa.Column("vessel_crm_access_token", sa.String(), nullable=True)
    )
    op.add_column("prospect", sa.Column("vessel_crm_id", sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("prospect", "vessel_crm_id")
    op.drop_column("client", "vessel_crm_access_token")
    # ### end Alembic commands ###
