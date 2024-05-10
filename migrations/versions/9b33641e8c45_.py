"""Added email_to_linkedin_connection, view_email, view_linkedin columns

Revision ID: 9b33641e8c45
Revises: c678597df604
Create Date: 2024-05-10 10:36:58.685006

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b33641e8c45'
down_revision = 'c678597df604'
branch_labels = None
depends_on = None


def upgrade():
    # Create the enum type first
    email_to_linkedin_connection_type = sa.Enum('RANDOM', 'ALL_PROSPECTS', 'OPENED_EMAIL_PROSPECTS_ONLY', 'CLICKED_LINK_PROSPECTS_ONLY', name='emailtolinkedinconnection')
    email_to_linkedin_connection_type.create(op.get_bind(), checkfirst=True)

    # Now add the columns
    op.add_column('client_archetype', sa.Column('view_linkedin', sa.Boolean(), nullable=True))
    op.add_column('client_archetype', sa.Column('view_email', sa.Boolean(), nullable=True))
    op.add_column('client_archetype', sa.Column('email_to_linkedin_connection', email_to_linkedin_connection_type, nullable=True))


def downgrade():
    # Drop the columns first
    op.drop_column('client_archetype', 'email_to_linkedin_connection')
    op.drop_column('client_archetype', 'view_email')
    op.drop_column('client_archetype', 'view_linkedin')
    
    # Drop the enum type
    email_to_linkedin_connection_type = sa.Enum('RANDOM', 'ALL_PROSPECTS', 'OPENED_EMAIL_PROSPECTS_ONLY', 'CLICKED_LINK_PROSPECTS_ONLY', name='emailtolinkedinconnection')
    email_to_linkedin_connection_type.drop(op.get_bind(), checkfirst=True)
