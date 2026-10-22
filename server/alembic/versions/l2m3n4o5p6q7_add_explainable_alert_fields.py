"""add_explainable_alert_fields

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-10-20 10:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'capacity_alerts' in tables:
        cols = [c["name"] for c in inspector.get_columns("capacity_alerts")]

        if "explanation_json" not in cols:
            op.add_column('capacity_alerts', sa.Column('explanation_json', sa.Text(), nullable=True))

        if "acknowledged_at" not in cols:
            op.add_column('capacity_alerts', sa.Column('acknowledged_at', sa.DateTime(), nullable=True))

        if "acknowledged_by_id" not in cols:
            op.add_column('capacity_alerts', sa.Column('acknowledged_by_id', sa.Integer(), nullable=True))
            try:
                op.create_foreign_key(
                    'fk_capacity_alerts_acknowledged_by_id_users',
                    'capacity_alerts', 'users',
                    ['acknowledged_by_id'], ['id'],
                    ondelete='SET NULL'
                )
            except Exception:
                pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'capacity_alerts' in tables:
        cols = [c["name"] for c in inspector.get_columns("capacity_alerts")]
        if "acknowledged_by_id" in cols:
            try:
                op.drop_constraint('fk_capacity_alerts_acknowledged_by_id_users', 'capacity_alerts', type_='foreignkey')
            except Exception:
                pass
            op.drop_column('capacity_alerts', 'acknowledged_by_id')

        if "acknowledged_at" in cols:
            op.drop_column('capacity_alerts', 'acknowledged_at')

        if "explanation_json" in cols:
            op.drop_column('capacity_alerts', 'explanation_json')
