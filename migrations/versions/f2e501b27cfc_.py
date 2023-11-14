"""Added status to individuals_upload

Revision ID: f2e501b27cfc
Revises: 639f5fc3ca75
Create Date: 2023-11-13 16:34:19.238590

"""
from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f2e501b27cfc'
down_revision = '639f5fc3ca75'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    individualsuploadstatus = postgresql.ENUM("FILTER_AND_UPLOAD", "COMPLETE", name="individualsuploadstatus")
    individualsuploadstatus.create(op.get_bind())
    op.add_column('individuals_upload', sa.Column('status', postgresql.ENUM('FILTER_AND_UPLOAD', 'COMPLETE', name='individualsuploadstatus'), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('individuals_upload', 'status')
    # ### end Alembic commands ###
