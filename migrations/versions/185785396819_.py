"""empty message

Revision ID: 185785396819
Revises: dad98adcac02
Create Date: 2022-11-02 18:23:04.181567

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '185785396819'
down_revision = 'dad98adcac02'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('email_customized_field',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('email_schema_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['email_schema_id'], ['email_schema.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('generated_message', sa.Column('email_customized_field_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'generated_message', 'email_customized_field', ['email_customized_field_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'generated_message', type_='foreignkey')
    op.drop_column('generated_message', 'email_customized_field_id')
    op.drop_table('email_customized_field')
    # ### end Alembic commands ###
