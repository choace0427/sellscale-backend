"""Add email bump frameworks

Revision ID: 82353fe07af8
Revises: 3a5e27823fea
Create Date: 2023-06-20 12:57:22.581737

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


# revision identifiers, used by Alembic.
revision = '82353fe07af8'
down_revision = '3a5e27823fea'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('bump_framework_email',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('objective', sa.String(length=255), nullable=True),
    sa.Column('email_blocks', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('client_sdr_id', sa.Integer(), nullable=True),
    sa.Column('client_archetype_id', sa.Integer(), nullable=True),
    sa.Column('overall_status', ENUM('PROSPECTED', 'SENT_OUTREACH', 'ACCEPTED', 'BUMPED', 'ACTIVE_CONVO', 'DEMO', 'REMOVED', name='prospectoverallstatus', create_type=False), nullable=True),
    sa.Column('substatus', sa.String(length=255), nullable=True),
    sa.Column('default', sa.Boolean(), nullable=False),
    sa.Column('email_length', sa.Enum('SHORT', 'MEDIUM', 'LONG', name='emaillength'), nullable=True),
    sa.Column('bumped_count', sa.Integer(), nullable=True),
    sa.Column('sellscale_default_generated', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['client_archetype_id'], ['client_archetype.id'], ),
    sa.ForeignKeyConstraint(['client_sdr_id'], ['client_sdr.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('bump_framework_email')
    # ### end Alembic commands ###
