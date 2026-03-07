"""add mining_yield

Revision ID: 99999999999a
Revises: 999999999999
Create Date: 2026-03-08 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '99999999999a'
down_revision = '999999999999'
branch_labels = None
depends_on = None

def upgrade():
    # Add mining_yield column to agents table
    # Using batch_alter_table for compatibility across DB types
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mining_yield', sa.Integer(), server_default='10', nullable=True))

def downgrade():
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.drop_column('mining_yield')
