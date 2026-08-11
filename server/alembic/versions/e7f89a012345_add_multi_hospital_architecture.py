"""Add multi hospital architecture and ward management

Revision ID: e7f89a012345
Revises: dcfccb5e0e45
Create Date: 2026-08-10 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = 'e7f89a012345'
down_revision: Union[str, None] = 'dcfccb5e0e45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create hospitals table
    op.create_table(
        'hospitals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hospitals_id'), 'hospitals', ['id'], unique=False)
    op.create_index(op.f('ix_hospitals_name'), 'hospitals', ['name'], unique=False)
    op.create_index(op.f('ix_hospitals_code'), 'hospitals', ['code'], unique=True)
    op.create_index(op.f('ix_hospitals_city'), 'hospitals', ['city'], unique=False)
    op.create_index(op.f('ix_hospitals_status'), 'hospitals', ['status'], unique=False)

    # 2. Insert default initial hospital record
    hospitals_table = sa.table(
        'hospitals',
        sa.column('name', sa.String),
        sa.column('code', sa.String),
        sa.column('address', sa.String),
        sa.column('city', sa.String),
        sa.column('state', sa.String),
        sa.column('country', sa.String),
        sa.column('status', sa.String),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime)
    )
    now = datetime.utcnow()
    op.bulk_insert(
        hospitals_table,
        [
            {
                'name': 'Apollo Medical Center',
                'code': 'H001',
                'address': '742 Evergreen Terrace',
                'city': 'Metropolis',
                'state': 'New York',
                'country': 'USA',
                'status': 'ACTIVE',
                'created_at': now,
                'updated_at': now,
            }
        ]
    )

    # 3. Add hospital_id to users table (nullable)
    op.add_column('users', sa.Column('hospital_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_users_hospital_id'), 'users', ['hospital_id'], unique=False)
    op.create_foreign_key('fk_users_hospital_id_hospitals', 'users', 'hospitals', ['hospital_id'], ['id'], ondelete='SET NULL')

    # Update existing users to belong to Apollo Medical Center (id 1)
    op.execute("UPDATE users SET hospital_id = 1 WHERE hospital_id IS NULL")

    # 4. Add hospital_id to wards table (nullable first for safe migration)
    op.add_column('wards', sa.Column('hospital_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_wards_hospital_id'), 'wards', ['hospital_id'], unique=False)
    op.create_foreign_key('fk_wards_hospital_id_hospitals', 'wards', 'hospitals', ['hospital_id'], ['id'], ondelete='CASCADE')

    # Update existing wards to belong to Apollo Medical Center (id 1)
    op.execute("UPDATE wards SET hospital_id = 1 WHERE hospital_id IS NULL")

    # Enforce non-nullable constraint on wards.hospital_id
    op.alter_column('wards', 'hospital_id', nullable=False)

    # Add composite unique constraint for hospital_id + name
    op.create_unique_constraint('uq_ward_hospital_name', 'wards', ['hospital_id', 'name'])


def downgrade() -> None:
    op.drop_constraint('uq_ward_hospital_name', 'wards', type_='unique')
    op.drop_constraint('fk_wards_hospital_id_hospitals', 'wards', type_='foreignkey')
    op.drop_index(op.f('ix_wards_hospital_id'), table_name='wards')
    op.drop_column('wards', 'hospital_id')

    op.drop_constraint('fk_users_hospital_id_hospitals', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_hospital_id'), table_name='users')
    op.drop_column('users', 'hospital_id')

    op.drop_index(op.f('ix_hospitals_status'), table_name='hospitals')
    op.drop_index(op.f('ix_hospitals_city'), table_name='hospitals')
    op.drop_index(op.f('ix_hospitals_code'), table_name='hospitals')
    op.drop_index(op.f('ix_hospitals_name'), table_name='hospitals')
    op.drop_index(op.f('ix_hospitals_id'), table_name='hospitals')
    op.drop_table('hospitals')
