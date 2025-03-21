"""empty message

Revision ID: dad98adcac02
Revises: d0180fca74b9
Create Date: 2022-11-02 18:15:45.366731

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dad98adcac02'
down_revision = 'd0180fca74b9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('email_schema_client_id_fkey', 'email_schema', type_='foreignkey')
    op.drop_constraint('email_schema_email_firstline_gnlp_model_id_fkey', 'email_schema', type_='foreignkey')
    op.drop_column('email_schema', 'client_id')
    op.drop_column('email_schema', 'email_firstline_gnlp_model_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('email_schema', sa.Column('email_firstline_gnlp_model_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('email_schema', sa.Column('client_id', sa.INTEGER(), autoincrement=False, nullable=False))
    op.create_foreign_key('email_schema_email_firstline_gnlp_model_id_fkey', 'email_schema', 'gnlp_models', ['email_firstline_gnlp_model_id'], ['id'])
    op.create_foreign_key('email_schema_client_id_fkey', 'email_schema', 'client', ['client_id'], ['id'])
    # ### end Alembic commands ###
