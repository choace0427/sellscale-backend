"""added channel warmup

Revision ID: f9e2a7006efe
Revises: 3c2d9bcb2062
Create Date: 2023-11-02 12:40:46.924994

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f9e2a7006efe"
down_revision = "3c2d9bcb2062"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "channel_warmup",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_sdr_id", sa.Integer(), nullable=True),
        sa.Column(
            "channel_type",
            postgresql.ENUM(
                "LINKEDIN",
                "EMAIL",
                "SELLSCALE",
                name="prospectchannels",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("daily_sent_count", sa.Integer(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("warmup_enabled", sa.Boolean(), nullable=False),
        sa.Column("reputation", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_sdr_id"],
            ["client_sdr.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("channel_warmup")
    # ### end Alembic commands ###
