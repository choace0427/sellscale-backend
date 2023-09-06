"""Added prospect_message_feedback

Revision ID: c076c880b599
Revises: d34405d78f4b
Create Date: 2023-09-06 15:46:46.682543

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c076c880b599'
down_revision = 'd34405d78f4b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('prospect_message_feedback',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('client_sdr_id', sa.Integer(), nullable=True),
    sa.Column('prospect_id', sa.Integer(), nullable=True),
    sa.Column('li_msg_id', sa.Integer(), nullable=True),
    sa.Column('email_msg_id', sa.Integer(), nullable=True),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('feedback', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['client_sdr_id'], ['client_sdr.id'], ),
    sa.ForeignKeyConstraint(['email_msg_id'], ['email_conversation_message.id'], ),
    sa.ForeignKeyConstraint(['li_msg_id'], ['linkedin_conversation_entry.id'], ),
    sa.ForeignKeyConstraint(['prospect_id'], ['prospect.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('prospect_message_feedback')
    # ### end Alembic commands ###
