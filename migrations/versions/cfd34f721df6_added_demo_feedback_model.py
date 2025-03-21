"""Added demo_feedback model

Revision ID: cfd34f721df6
Revises: 6386c539174e
Create Date: 2023-05-08 14:08:49.741615

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cfd34f721df6'
down_revision = '6386c539174e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('demo_feedback',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=True),
    sa.Column('client_sdr_id', sa.Integer(), nullable=True),
    sa.Column('prospect_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('rating', sa.String(), nullable=True),
    sa.Column('feedback', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['client_id'], ['client.id'], ),
    sa.ForeignKeyConstraint(['client_sdr_id'], ['client_sdr.id'], ),
    sa.ForeignKeyConstraint(['prospect_id'], ['prospect.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('demo_feedback')
    # ### end Alembic commands ###
