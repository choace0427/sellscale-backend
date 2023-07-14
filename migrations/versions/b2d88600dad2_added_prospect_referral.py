"""Added prospect referral

Revision ID: b2d88600dad2
Revises: af6d22bdd37b
Create Date: 2023-07-13 19:46:42.486469

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2d88600dad2'
down_revision = 'af6d22bdd37b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('prospect_referral',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('referral_id', sa.Integer(), nullable=False),
    sa.Column('referred_id', sa.Integer(), nullable=False),
    sa.Column('meta_data', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['referral_id'], ['prospect.id'], ),
    sa.ForeignKeyConstraint(['referred_id'], ['prospect.id'], ),
    sa.PrimaryKeyConstraint('referral_id', 'referred_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('prospect_referral')
    # ### end Alembic commands ###