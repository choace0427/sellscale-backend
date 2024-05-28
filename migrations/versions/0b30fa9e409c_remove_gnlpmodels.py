"""Remove GNLPModels

Revision ID: 0b30fa9e409c
Revises: f71c5fa9fa2f
Create Date: 2024-05-28 11:52:54.480800

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0b30fa9e409c"
down_revision = "f71c5fa9fa2f"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "generated_message_gnlp_model_id_fkey", "generated_message", type_="foreignkey"
    )
    op.drop_column("generated_message", "gnlp_model_id")

    op.drop_table("gnlp_models_fine_tune_jobs")
    op.drop_table("gnlp_models")

    op.execute("DROP TYPE IF EXISTS gnlpmodeltype CASCADE;")
    op.execute("DROP TYPE IF EXISTS gnlpfinetunejobstatuses CASCADE;")
    op.execute("DROP TYPE IF EXISTS modelprovider CASCADE;")

    pass


def downgrade():
    # No downgrade, we don't want to keep this data around

    pass
