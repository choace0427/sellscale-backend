"""Added persona table

Revision ID: 39f31d966956
Revises: 302da5c7ecec
Create Date: 2024-04-09 13:15:43.643693

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "39f31d966956"
down_revision = "302da5c7ecec"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "persona",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("client_sdr_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("saved_apollo_query_id", sa.Integer(), nullable=True),
        sa.Column(
            "stack_ranked_message_generation_configuration_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["client.id"],
        ),
        sa.ForeignKeyConstraint(
            ["client_sdr_id"],
            ["client_sdr.id"],
        ),
        sa.ForeignKeyConstraint(
            ["saved_apollo_query_id"],
            ["saved_apollo_query.id"],
        ),
        sa.ForeignKeyConstraint(
            ["stack_ranked_message_generation_configuration_id"],
            ["stack_ranked_message_generation_configuration.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("persona")
    # ### end Alembic commands ###
