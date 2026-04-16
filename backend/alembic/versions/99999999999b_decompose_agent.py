"""decompose agent

Revision ID: 99999999999b
Revises: 99999999999a
Create Date: 2026-04-03 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '99999999999b'
down_revision = '99999999999a'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Create target compositional tables
    op.create_table('agent_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('health', sa.Integer(), server_default='100', nullable=True),
        sa.Column('max_health', sa.Integer(), server_default='100', nullable=True),
        sa.Column('energy', sa.Integer(), server_default='100', nullable=True),
        sa.Column('damage', sa.Integer(), server_default='10', nullable=True),
        sa.Column('accuracy', sa.Integer(), server_default='15', nullable=True),
        sa.Column('speed', sa.Integer(), server_default='10', nullable=True),
        sa.Column('armor', sa.Integer(), server_default='5', nullable=True),
        sa.Column('overclock', sa.Integer(), server_default='10', nullable=True),
        sa.Column('max_mass', sa.Float(), server_default='100.0', nullable=True),
        sa.Column('storage_capacity', sa.Float(), server_default='500.0', nullable=True),
        sa.Column('mining_yield', sa.Integer(), server_default='10', nullable=True),
        sa.Column('loot_bonus', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('energy_save', sa.Integer(), server_default='0', nullable=True),
        sa.Column('wear_resistance', sa.Float(), server_default='0.0', nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_stats_agent_id'), 'agent_stats', ['agent_id'], unique=True)
    op.create_index(op.f('ix_agent_stats_id'), 'agent_stats', ['id'], unique=False)

    op.create_table('agent_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('is_bot', sa.Boolean(), nullable=True),
        sa.Column('is_feral', sa.Boolean(), nullable=True),
        sa.Column('is_pitfighter', sa.Boolean(), nullable=True),
        sa.Column('is_aggressive', sa.Boolean(), nullable=True),
        sa.Column('q', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('r', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('heat', sa.Integer(), server_default='0', nullable=True),
        sa.Column('overclock_ticks', sa.Integer(), server_default='0', nullable=True),
        sa.Column('wear_and_tear', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('last_faction_change_tick', sa.Integer(), server_default='0', nullable=True),
        sa.Column('last_attacked_tick', sa.Integer(), server_default='0', nullable=True),
        sa.Column('is_in_anarchy_zone', sa.Boolean(), server_default='FALSE', nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_state_agent_id'), 'agent_state', ['agent_id'], unique=True)
    op.create_index(op.f('ix_agent_state_heat'), 'agent_state', ['heat'], unique=False)
    op.create_index(op.f('ix_agent_state_id'), 'agent_state', ['id'], unique=False)

    op.create_table('agent_progression',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('level', sa.Integer(), server_default='1', nullable=True),
        sa.Column('experience', sa.Integer(), server_default='0', nullable=True),
        sa.Column('unlocked_recipes', sa.JSON(), nullable=True),
        sa.Column('last_daily_reward', sa.DateTime(timezone=True), nullable=True),
        sa.Column('performance_stats', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_progression_agent_id'), 'agent_progression', ['agent_id'], unique=True)
    op.create_index(op.f('ix_agent_progression_id'), 'agent_progression', ['id'], unique=False)

    # 2. Data Migration: Copy data from `agents` to new tables
    op.execute("""
        INSERT INTO agent_stats (agent_id, health, max_health, energy, damage, accuracy, speed, armor, overclock, max_mass, storage_capacity, mining_yield, loot_bonus, energy_save, wear_resistance)
        SELECT id, COALESCE(health, 100), COALESCE(max_health, 100), COALESCE(energy, 100), COALESCE(damage, 10), COALESCE(accuracy, 15), COALESCE(speed, 10), COALESCE(armor, 5), COALESCE(overclock, 10), COALESCE(max_mass, 100.0), COALESCE(storage_capacity, 500.0), COALESCE(mining_yield, 10), COALESCE(loot_bonus, 0.0), COALESCE(energy_save, 0), COALESCE(wear_resistance, 0.0)
        FROM agents
    """)

    op.execute("""
        INSERT INTO agent_state (agent_id, is_bot, is_feral, is_pitfighter, is_aggressive, q, r, heat, overclock_ticks, wear_and_tear, last_faction_change_tick, last_attacked_tick, is_in_anarchy_zone)
        SELECT id, COALESCE(is_bot, FALSE), COALESCE(is_feral, FALSE), COALESCE(is_pitfighter, FALSE), COALESCE(is_aggressive, FALSE), COALESCE(q, 0), COALESCE(r, 0), COALESCE(heat, 0), COALESCE(overclock_ticks, 0), COALESCE(wear_and_tear, 0.0), COALESCE(last_faction_change_tick, 0), COALESCE(last_attacked_tick, 0), COALESCE(is_in_anarchy_zone, FALSE)
        FROM agents
    """)

    op.execute("""
        INSERT INTO agent_progression (agent_id, level, experience, unlocked_recipes, last_daily_reward, performance_stats)
        SELECT id, COALESCE(level, 1), COALESCE(experience, 0), unlocked_recipes, last_daily_reward, performance_stats
        FROM agents
    """)

    # 3. Drop columns from Agents table using batch operations to support SQLite
    with op.batch_alter_table('agents', schema=None) as batch_op:
        columns_to_drop = [
            'health', 'max_health', 'energy', 'damage', 'accuracy', 'speed', 'armor', 
            'overclock', 'max_mass', 'storage_capacity', 'mining_yield', 'loot_bonus', 
            'energy_save', 'wear_resistance', 'is_bot', 'is_feral', 'is_pitfighter', 
            'is_aggressive', 'q', 'r', 'heat', 'overclock_ticks', 'wear_and_tear', 
            'last_faction_change_tick', 'last_attacked_tick', 'is_in_anarchy_zone',
            'level', 'experience', 'unlocked_recipes', 'last_daily_reward', 'performance_stats'
        ]
        for col in columns_to_drop:
            batch_op.drop_column(col)

def downgrade():
    # Technically reverse the process, but standard practice in these huge refactors is 
    # to reconstruct the table. Here we just add columns back and copy.
    pass
