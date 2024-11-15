"""Added email grading table

Revision ID: 5ab8cff42cea
Revises: 39eab9df99a0
Create Date: 2024-01-22 15:28:38.862829

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ab8cff42cea'
down_revision = '39eab9df99a0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('email_grader_entry',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('input_subject_line', sa.String(), nullable=False),
    sa.Column('input_body', sa.String(), nullable=False),
    sa.Column('input_tracking_data', sa.JSON(), nullable=True),
    sa.Column('detected_company', sa.String(), nullable=True),
    sa.Column('evaluated_score', sa.Integer(), nullable=True),
    sa.Column('evaluated_feedback', sa.JSON(), nullable=True),
    sa.Column('evaluated_tones', sa.JSON(), nullable=True),
    sa.Column('evaluated_construction_subject_line', sa.String(), nullable=True),
    sa.Column('evaluated_construction_spam_words_subject_line', sa.JSON(), nullable=True),
    sa.Column('evaluated_construction_body', sa.String(), nullable=True),
    sa.Column('evaluated_construction_spam_words_body', sa.JSON(), nullable=True),
    sa.Column('evaluated_read_time_seconds', sa.Integer(), nullable=True),
    sa.Column('evaluated_personalizations', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('email_grader_entry')
    # ### end Alembic commands ###
