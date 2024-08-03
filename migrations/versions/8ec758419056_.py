"""Add company icp scoring and reason to prospect
Add segment Id to icp_scoring_ruleset

Revision ID: 8ec758419056
Revises: bc7c9160a6fb
Create Date: 2024-08-01 15:26:36.952850

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ec758419056'
down_revision = 'bc7c9160a6fb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('icp_scoring_ruleset', sa.Column('segment_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'icp_scoring_ruleset', 'segment', ['segment_id'], ['id'])
    op.add_column('prospect', sa.Column('icp_fit_reason_v2', sa.JSON(), nullable=True))
    op.add_column('prospect', sa.Column('icp_company_fit_score', sa.Integer(), nullable=True))
    op.add_column('prospect', sa.Column('icp_company_fit_reason', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prospect', 'icp_company_fit_reason')
    op.drop_column('prospect', 'icp_company_fit_score')
    op.drop_column('prospect', 'icp_fit_reason_v2')
    op.drop_constraint(None, 'icp_scoring_ruleset', type_='foreignkey')
    op.drop_column('icp_scoring_ruleset', 'segment_id')
    # ### end Alembic commands ###