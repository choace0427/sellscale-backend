"""Added ai_generated to li and email messages

Revision ID: c66886c67115
Revises: 95a6bd43ccd5
Create Date: 2023-05-16 10:56:13.936794

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c66886c67115'
down_revision = '95a6bd43ccd5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('email_conversation_message', sa.Column('ai_generated', sa.Boolean(), nullable=True))
    op.add_column('linkedin_conversation_entry', sa.Column('ai_generated', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('linkedin_conversation_entry', 'ai_generated')
    op.drop_column('email_conversation_message', 'ai_generated')
    # ### end Alembic commands ###
