"""empty message

Revision ID: 23c6b1e80fa2
Revises: b772d8df7abc
Create Date: 2022-11-02 21:46:46.398679

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '23c6b1e80fa2'
down_revision = 'b772d8df7abc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('prospect_email',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email_schema_id', sa.Integer(), nullable=False),
    sa.Column('prospect_id', sa.Integer(), nullable=False),
    sa.Column('personalized_first_line', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['email_schema_id'], ['email_schema.id'], ),
    sa.ForeignKeyConstraint(['personalized_first_line'], ['generated_message.id'], ),
    sa.ForeignKeyConstraint(['prospect_id'], ['prospect.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('email_customized_field')
    op.add_column('email_schema', sa.Column('personalized_first_line_gnlp_model_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'email_schema', 'gnlp_models', ['personalized_first_line_gnlp_model_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'email_schema', type_='foreignkey')
    op.drop_column('email_schema', 'personalized_first_line_gnlp_model_id')
    op.create_table('email_customized_field',
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('email_schema_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('email_customized_field_type', postgresql.ENUM('EMAIL_FIRST_LINE', name='emailcustomizedfieldtypes'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['email_schema_id'], ['email_schema.id'], name='email_customized_field_email_schema_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='email_customized_field_pkey')
    )
    op.drop_table('prospect_email')
    # ### end Alembic commands ###
