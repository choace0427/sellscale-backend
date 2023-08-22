"""Create EmailSubjectLineTemplate

Revision ID: fef5e4848ce9
Revises: a832636fb413
Create Date: 2023-08-21 11:27:11.446694

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fef5e4848ce9'
down_revision = 'a832636fb413'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('email_subject_line_template',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('subject_line', sa.String(length=255), nullable=False),
    sa.Column('client_sdr_id', sa.Integer(), nullable=True),
    sa.Column('client_archetype_id', sa.Integer(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('times_used', sa.Integer(), nullable=False),
    sa.Column('times_accepted', sa.Integer(), nullable=False),
    sa.Column('sellscale_generated', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['client_archetype_id'], ['client_archetype.id'], ),
    sa.ForeignKeyConstraint(['client_sdr_id'], ['client_sdr.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('email_sequence_step', sa.Column('template', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('email_sequence_step', 'template')
    op.drop_table('email_subject_line_template')
    # ### end Alembic commands ###
