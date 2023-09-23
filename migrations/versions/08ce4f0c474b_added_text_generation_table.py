"""Added text_generation table

Revision ID: 08ce4f0c474b
Revises: 5dd362c163e3
Create Date: 2023-09-12 14:41:10.450137

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '08ce4f0c474b'
down_revision = '5dd362c163e3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('text_generation',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('prospect_id', sa.Integer(), nullable=False),
    sa.Column('client_sdr_id', sa.Integer(), nullable=False),
    sa.Column('prompt', sa.String(), nullable=False),
    sa.Column('completion', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('human_edited', sa.Boolean(), nullable=False),
    sa.Column('model_provider', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['client_sdr_id'], ['client_sdr.id'], ),
    sa.ForeignKeyConstraint(['prospect_id'], ['prospect.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('text_generation')
    # ### end Alembic commands ###