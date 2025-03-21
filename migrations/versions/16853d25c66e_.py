""" Create adversary training point table.

Revision ID: 16853d25c66e
Revises: 38826ce0bf0a
Create Date: 2022-12-20 13:01:35.951051

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '16853d25c66e'
down_revision = '38826ce0bf0a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('adversary_training_point',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('generated_message_id', sa.Integer(), nullable=False),
    sa.Column('prompt', sa.String(), nullable=False),
    sa.Column('completion', sa.String(), nullable=False),
    sa.Column('mistake_description', sa.String(), nullable=False),
    sa.Column('fix_instuctions', sa.String(), nullable=False),
    sa.Column('use_in_training', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['generated_message_id'], ['generated_message.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('adversary_training_point')
    # ### end Alembic commands ###
