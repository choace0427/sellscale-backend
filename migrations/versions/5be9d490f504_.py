"""Added selix_action_call table

Revision ID: 5be9d490f504
Revises: 9dd0d1ff9ab9
Create Date: 2024-08-05 12:58:01.337568

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5be9d490f504'
down_revision = '9dd0d1ff9ab9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('selix_action_call',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('selix_session_id', sa.Integer(), nullable=False),
    sa.Column('action_title', sa.String(length=255), nullable=True),
    sa.Column('action_description', sa.String(), nullable=True),
    sa.Column('action_function', sa.String(length=255), nullable=True),
    sa.Column('action_params', sa.JSON(), nullable=True),
    sa.Column('actual_completion_time', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['selix_session_id'], ['selix_session.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('selix_action_call')
    # ### end Alembic commands ###
