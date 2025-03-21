"""Added generated message queue table

Revision ID: d28e2b1e09e5
Revises: c66886c67115
Create Date: 2023-05-16 11:13:43.656564

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd28e2b1e09e5'
down_revision = 'c66886c67115'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('generated_message_queue',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('client_sdr_id', sa.Integer(), nullable=False),
    sa.Column('nylas_message_id', sa.String(), nullable=True),
    sa.Column('li_message_urn_id', sa.String(), nullable=True),
    sa.Column('scrape_time', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['client_sdr_id'], ['client_sdr.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generated_message_queue_li_message_urn_id'), 'generated_message_queue', ['li_message_urn_id'], unique=True)
    op.create_index(op.f('ix_generated_message_queue_nylas_message_id'), 'generated_message_queue', ['nylas_message_id'], unique=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_generated_message_queue_nylas_message_id'), table_name='generated_message_queue')
    op.drop_index(op.f('ix_generated_message_queue_li_message_urn_id'), table_name='generated_message_queue')
    op.drop_table('generated_message_queue')
    # ### end Alembic commands ###
