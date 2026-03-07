"""rename_stats

Revision ID: 999999999999
Revises: 
Create Date: 2026-03-05 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '999999999999'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Attempt to rename columns carefully. Note: SQLite doesn't natively support all ALter commands easily.
    # This migration works natively on PostgreSQL for Oracle cloud.
    
    # 1. Rename existing stats on 'agents'
    try:
        op.alter_column('agents', 'structure', new_column_name='health', existing_type=sa.Float())
    except Exception as e:
        print("Column 'structure' might already be renamed to 'health'. Exception:", e)

    try:
        op.alter_column('agents', 'max_structure', new_column_name='max_health', existing_type=sa.Float())
    except Exception as e:
        print("Column 'max_structure' might already be renamed to 'max_health'. Exception:", e)

    try:
        op.alter_column('agents', 'kinetic_force', new_column_name='damage', existing_type=sa.Float())
    except Exception as e:
        print("Column 'kinetic_force' might already be renamed to 'damage'. Exception:", e)

    try:
        op.alter_column('agents', 'logic_precision', new_column_name='accuracy', existing_type=sa.Float())
    except Exception as e:
        print("Column 'logic_precision' might already be renamed to 'accuracy'. Exception:", e)

    try:
        op.alter_column('agents', 'integrity', new_column_name='armor', existing_type=sa.Float())
    except Exception as e:
        print("Column 'integrity' might already be renamed to 'armor'. Exception:", e)

    try:
        op.alter_column('agents', 'capacitor', new_column_name='energy', existing_type=sa.Float())
    except Exception as e:
        print("Column 'capacitor' might already be renamed to 'energy'. Exception:", e)
    
    # 2. Add speed column
    try:
        op.add_column('agents', sa.Column('speed', sa.Float(), nullable=True))
        op.execute("UPDATE agents SET speed = 10.0 WHERE speed IS NULL")
    except Exception as e:
        print("Column 'speed' might already exist. Exception:", e)
    
    # 3. Create Arena Profile table if it doesn't exist
    try:
        op.create_table(
            'arena_profiles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('fighter_name', sa.String(64), nullable=True),
            sa.Column('elo', sa.Integer(), server_default='1200'),
            sa.Column('wins', sa.Integer(), server_default='0'),
            sa.Column('losses', sa.Integer(), server_default='0'),
            sa.Column('health', sa.Float(), server_default='100.0'),
            sa.Column('max_health', sa.Float(), server_default='100.0'),
            sa.Column('damage', sa.Float(), server_default='10.0'),
            sa.Column('accuracy', sa.Float(), server_default='10.0'),
            sa.Column('speed', sa.Float(), server_default='10.0'),
            sa.Column('armor', sa.Float(), server_default='0.0'),
            sa.Column('energy', sa.Float(), server_default='100.0')
        )
    except Exception as e:
        print("Arena profiles table might already exist. Exception:", e)

    # 4. Arena Logs Table
    try:
        op.create_table(
            'arena_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id')),
            sa.Column('opponent_id', sa.Integer(), nullable=True),
            sa.Column('opponent_name', sa.String(), nullable=True),
            sa.Column('opponent_elo', sa.Integer(), nullable=True),
            sa.Column('event', sa.String()),
            sa.Column('details', sa.JSON()),
            sa.Column('elo_change', sa.Integer()),
            sa.Column('winner_id', sa.Integer(), nullable=True),
            sa.Column('time', sa.DateTime())
        )
    except Exception as e:
        print("Arena logs table might already exist. Exception:", e)
        
    # 5. Arena Gear Table
    try:
        op.create_table(
            'arena_gear',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id')),
            sa.Column('part_id', sa.Integer()),
            sa.Column('type', sa.String()),
            sa.Column('name', sa.String()),
            sa.Column('stats', sa.JSON()),
            sa.Column('rarity', sa.String()),
            sa.Column('level', sa.Integer()),
            sa.Column('durability', sa.Float())
        )
    except Exception as e:
        print("Arena gear table might already exist. Exception:", e)

def downgrade():
    op.drop_column('agents', 'speed')
    
    op.alter_column('agents', 'health', new_column_name='structure', existing_type=sa.Float())
    op.alter_column('agents', 'max_health', new_column_name='max_structure', existing_type=sa.Float())
    op.alter_column('agents', 'damage', new_column_name='kinetic_force', existing_type=sa.Float())
    op.alter_column('agents', 'accuracy', new_column_name='logic_precision', existing_type=sa.Float())
    op.alter_column('agents', 'armor', new_column_name='integrity', existing_type=sa.Float())
    op.alter_column('agents', 'energy', new_column_name='capacitor', existing_type=sa.Float())
    
    op.drop_table('arena_gear')
    op.drop_table('arena_logs')
    op.drop_table('arena_profiles')
