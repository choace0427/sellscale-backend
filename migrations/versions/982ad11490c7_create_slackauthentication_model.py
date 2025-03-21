"""Create SlackAuthentication model

Revision ID: 982ad11490c7
Revises: 808ac38c3df6
Create Date: 2024-01-24 14:16:01.616564

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "982ad11490c7"
down_revision = "808ac38c3df6"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "slack_authentication",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("client_sdr_id", sa.Integer(), nullable=True),
        sa.Column(
            "slack_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("slack_access_token", sa.String(length=255), nullable=False),
        sa.Column("slack_token_type", sa.String(length=255), nullable=False),
        sa.Column("slack_scope", sa.String(), nullable=False),
        sa.Column("slack_bot_user_id", sa.String(length=255), nullable=False),
        sa.Column("slack_app_id", sa.String(length=255), nullable=False),
        sa.Column("slack_team_name", sa.String(), nullable=True),
        sa.Column("slack_team_id", sa.String(length=255), nullable=True),
        sa.Column("slack_enterprise_name", sa.String(), nullable=True),
        sa.Column("slack_enterprise_id", sa.String(length=255), nullable=True),
        sa.Column("slack_authed_user_id", sa.String(length=255), nullable=True),
        sa.Column("slack_authed_user_scope", sa.String(), nullable=True),
        sa.Column(
            "slack_authed_user_access_token", sa.String(length=255), nullable=True
        ),
        sa.Column("slack_authed_user_token_type", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["client.id"],
        ),
        sa.ForeignKeyConstraint(
            ["client_sdr_id"],
            ["client_sdr.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("slack_authentication")
    # ### end Alembic commands ###
