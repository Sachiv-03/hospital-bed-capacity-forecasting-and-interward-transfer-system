"""add_occupancy_snapshots_and_capacity_alerts

Revision ID: aa9de7400d86
Revises: f1a2b3c4d5e6
Create Date: 2026-08-13 22:05:22.784370

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa9de7400d86'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if tables exist before creating
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'occupancy_snapshots' not in tables:
        op.create_table(
            'occupancy_snapshots',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('hospital_id', sa.Integer(), nullable=False),
            sa.Column('ward_id', sa.Integer(), nullable=False),
            sa.Column('snapshot_time', sa.DateTime(), nullable=False),
            sa.Column('total_beds', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('occupied_beds', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('available_beds', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('cleaning_beds', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('reserved_beds', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('maintenance_beds', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('occupancy_percentage', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('hospital_id', 'ward_id', 'snapshot_time', name='uq_hospital_ward_snapshot_time')
        )
        op.create_index('ix_occupancy_snapshots_id', 'occupancy_snapshots', ['id'], unique=False)
        op.create_index('ix_occupancy_snapshots_hospital_id', 'occupancy_snapshots', ['hospital_id'], unique=False)
        op.create_index('ix_occupancy_snapshots_ward_id', 'occupancy_snapshots', ['ward_id'], unique=False)
        op.create_index('ix_occupancy_snapshots_snapshot_time', 'occupancy_snapshots', ['snapshot_time'], unique=False)

    if 'capacity_alerts' not in tables:
        op.create_table(
            'capacity_alerts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('hospital_id', sa.Integer(), nullable=False),
            sa.Column('ward_id', sa.Integer(), nullable=False),
            sa.Column('alert_type', sa.String(length=50), nullable=False),
            sa.Column('severity', sa.String(length=50), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('trigger_value', sa.Float(), nullable=False),
            sa.Column('threshold_value', sa.Float(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_capacity_alerts_id', 'capacity_alerts', ['id'], unique=False)
        op.create_index('ix_capacity_alerts_hospital_id', 'capacity_alerts', ['hospital_id'], unique=False)
        op.create_index('ix_capacity_alerts_ward_id', 'capacity_alerts', ['ward_id'], unique=False)
        op.create_index('ix_capacity_alerts_alert_type', 'capacity_alerts', ['alert_type'], unique=False)
        op.create_index('ix_capacity_alerts_severity', 'capacity_alerts', ['severity'], unique=False)
        op.create_index('ix_capacity_alerts_status', 'capacity_alerts', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('capacity_alerts')
    op.drop_table('occupancy_snapshots')
