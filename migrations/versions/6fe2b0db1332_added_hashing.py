"""Added hashing

Revision ID: 6fe2b0db1332
Revises: 76f8bf1e04ad
Create Date: 2024-02-15 10:04:24.430213

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6fe2b0db1332'
down_revision = '76f8bf1e04ad'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('icp_scoring_ruleset', sa.Column('hash', sa.String(), nullable=True))
    op.add_column('prospect', sa.Column('icp_fit_last_hash', sa.String(), nullable=True))
    op.add_column('research_point_type', sa.Column('archetype_id', sa.Integer(), nullable=True))
    op.add_column('research_point_type', sa.Column('category', sa.String(), nullable=True))
    op.create_foreign_key(None, 'research_point_type', 'client_archetype', ['archetype_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'research_point_type', type_='foreignkey')
    op.drop_column('research_point_type', 'category')
    op.drop_column('research_point_type', 'archetype_id')
    op.drop_column('prospect', 'icp_fit_last_hash')
    op.drop_column('icp_scoring_ruleset', 'hash')
    # ### end Alembic commands ###