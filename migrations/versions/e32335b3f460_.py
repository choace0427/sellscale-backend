"""Add segment tags table

Revision ID: e32335b3f460
Revises: 824c860f9377
Create Date: 2024-05-07 14:06:51.751061

"""
from alembic import op
import sqlalchemy as sa


revision = 'e32335b3f460'
down_revision = '824c860f9377'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('segment_tags',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('color', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['client.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('segment_tags')
