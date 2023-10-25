"""Switch meta_data to jsonb

Revision ID: a8854c87d6e2
Revises: 85221aedab12
Create Date: 2023-10-25 10:59:09.887591

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a8854c87d6e2'
down_revision = '85221aedab12'
branch_labels = None
depends_on = None


def upgrade():
    # Change the data type of the column from JSON to JSONB
    connection = op.get_bind()
    connection.execute(text('ALTER TABLE process_queue ALTER COLUMN meta_data TYPE JSONB USING meta_data::jsonb'))

def downgrade():
    # Reverse the change: Change the data type of the column from JSONB to JSON
    connection = op.get_bind()
    connection.execute(text('ALTER TABLE process_queue ALTER COLUMN meta_data TYPE JSON USING meta_data::json'))
