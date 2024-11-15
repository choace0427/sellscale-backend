"""Added error_message to generated_message_job

Revision ID: 9dfe8dc970c7
Revises: 6107ed195d81
Create Date: 2023-02-27 10:15:56.234312

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9dfe8dc970c7"
down_revision = "6107ed195d81"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "generated_message_job", sa.Column("error_message", sa.String(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("generated_message_job", "error_message")
    # ### end Alembic commands ###
