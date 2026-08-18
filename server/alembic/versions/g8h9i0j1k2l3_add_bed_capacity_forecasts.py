"""add_bed_capacity_forecasts

Revision ID: g8h9i0j1k2l3
Revises: aa9de7400d86
Create Date: 2026-08-17 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g8h9i0j1k2l3'
down_revision: Union[str, None] = 'aa9de7400d86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'bed_capacity_forecasts' not in tables:
        op.create_table(
            'bed_capacity_forecasts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('hospital_id', sa.Integer(), nullable=False),
            sa.Column('ward_id', sa.Integer(), nullable=False),
            sa.Column('forecast_date', sa.Date(), nullable=False),
            sa.Column('generated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('horizon_days', sa.Integer(), nullable=False, server_default='7'),
            sa.Column('predicted_occupied_beds', sa.Float(), nullable=False),
            sa.Column('predicted_occupancy_percentage', sa.Float(), nullable=False),
            sa.Column('lower_bound', sa.Float(), nullable=True),
            sa.Column('upper_bound', sa.Float(), nullable=True),
            sa.Column('risk_level', sa.String(length=20), nullable=False, server_default='NORMAL'),
            sa.Column('model_name', sa.String(length=50), nullable=False, server_default='SARIMA'),
            sa.Column('model_version', sa.String(length=20), nullable=False, server_default='1.0'),
            sa.Column('training_data_start', sa.Date(), nullable=True),
            sa.Column('training_data_end', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_bed_capacity_forecasts_id', 'bed_capacity_forecasts', ['id'], unique=False)
        op.create_index('ix_bed_capacity_forecasts_hospital_id', 'bed_capacity_forecasts', ['hospital_id'], unique=False)
        op.create_index('ix_bed_capacity_forecasts_ward_id', 'bed_capacity_forecasts', ['ward_id'], unique=False)
        op.create_index('ix_bed_capacity_forecasts_forecast_date', 'bed_capacity_forecasts', ['forecast_date'], unique=False)
        op.create_index('ix_bed_capacity_forecasts_generated_at', 'bed_capacity_forecasts', ['generated_at'], unique=False)
        op.create_index('ix_bed_capacity_forecasts_risk_level', 'bed_capacity_forecasts', ['risk_level'], unique=False)
        op.create_index('ix_bed_capacity_forecasts_ward_date', 'bed_capacity_forecasts', ['ward_id', 'forecast_date'], unique=False)


def downgrade() -> None:
    op.drop_table('bed_capacity_forecasts')
