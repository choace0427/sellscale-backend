"""Add MergeWebhookPayload

Revision ID: b5ee1948a195
Revises: 3a1b688e861d
Create Date: 2024-04-22 13:56:21.421567

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b5ee1948a195"
down_revision = "3a1b688e861d"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "merge_webhook_payload",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "merge_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "merge_webhook_type",
            sa.Enum("CRM_OPPORTUNITY_UPDATED", name="mergewebhooktype"),
            nullable=False,
        ),
        sa.Column(
            "processing_status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "SUCCEEDED",
                "INELIGIBLE",
                "FAILED",
                name="mergewebhookprocessingstatus",
            ),
            nullable=False,
        ),
        sa.Column("processing_fail_reason", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("merge_webhook_payload")
    # ### end Alembic commands ###
