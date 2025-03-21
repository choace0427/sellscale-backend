"""Add PhantomBusterSalesNavigatorConfig and PhantomBusterSalesNavigatorConfig

Revision ID: b0f83a993c1d
Revises: 89e80ca71ff7
Create Date: 2023-07-11 12:02:24.723082

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0f83a993c1d'
down_revision = '89e80ca71ff7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('phantom_buster_sales_navigator_config',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=True),
    sa.Column('client_sdr_id', sa.Integer(), nullable=True),
    sa.Column('common_pool', sa.Boolean(), nullable=True),
    sa.Column('phantom_name', sa.String(), nullable=True),
    sa.Column('phantom_uuid', sa.String(), nullable=True),
    sa.Column('linkedin_session_cookie', sa.String(), nullable=True),
    sa.Column('daily_trigger_count', sa.Integer(), nullable=True),
    sa.Column('daily_prospect_count', sa.Integer(), nullable=True),
    sa.Column('in_use', sa.Boolean(), nullable=True),
    sa.Column('last_run_date', sa.DateTime(), nullable=True),
    sa.Column('error_message', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['client_id'], ['client.id'], ),
    sa.ForeignKeyConstraint(['client_sdr_id'], ['client_sdr.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('phantom_buster_sales_navigator_launch',
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sales_navigator_config_id', sa.Integer(), nullable=True),
    sa.Column('client_sdr_id', sa.Integer(), nullable=True),
    sa.Column('sales_navigator_url', sa.String(), nullable=True),
    sa.Column('scrape_count', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('NEEDS_AGENT', 'QUEUED', 'RUNNING', 'SUCCESS', 'FAILED', name='salesnavigatorlaunchstatus'), nullable=True),
    sa.Column('pb_container_id', sa.String(), nullable=True),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('launch_date', sa.DateTime(), nullable=True),
    sa.Column('error_message', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['client_sdr_id'], ['client_sdr.id'], ),
    sa.ForeignKeyConstraint(['sales_navigator_config_id'], ['phantom_buster_sales_navigator_config.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('phantom_buster_sales_navigator_launch')
    op.drop_table('phantom_buster_sales_navigator_config')
    # ### end Alembic commands ###
