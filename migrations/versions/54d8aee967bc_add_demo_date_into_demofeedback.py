"""Add demo_date into DemoFeedback

Revision ID: 54d8aee967bc
Revises: 8b5cc3659753
Create Date: 2023-08-02 12:51:04.294931

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54d8aee967bc'
down_revision = '8b5cc3659753'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('demo_feedback', sa.Column('demo_date', sa.DateTime(), nullable=True))
    op.add_column('demo_feedback', sa.Column('next_demo_date', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('demo_feedback', 'demo_date')
    op.drop_column('demo_feedback', 'next_demo_date')
    # ### end Alembic commands ###
