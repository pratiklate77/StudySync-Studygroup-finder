"""Initial admin service tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create admin_user table
    op.create_table('admin_user',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
    sa.Column('login_count', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_user_email'), 'admin_user', ['email'], unique=True)
    op.create_index(op.f('ix_admin_user_id'), 'admin_user', ['id'], unique=False)

    # Create admin_action table
    op.create_table('admin_action',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=True),
    sa.Column('target_id', sa.String(length=255), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['admin_user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_action_action'), 'admin_action', ['action'], unique=False)
    op.create_index(op.f('ix_admin_action_admin_id'), 'admin_action', ['admin_id'], unique=False)
    op.create_index(op.f('ix_admin_action_id'), 'admin_action', ['id'], unique=False)
    op.create_index(op.f('ix_admin_action_target_id'), 'admin_action', ['target_id'], unique=False)
    op.create_index(op.f('ix_admin_action_target_type'), 'admin_action', ['target_type'], unique=False)

    # Create platform_setting table
    op.create_table('platform_setting',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('is_public', sa.Boolean(), nullable=False),
    sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_platform_setting_category'), 'platform_setting', ['category'], unique=False)
    op.create_index(op.f('ix_platform_setting_id'), 'platform_setting', ['id'], unique=False)
    op.create_index(op.f('ix_platform_setting_key'), 'platform_setting', ['key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_platform_setting_key'), table_name='platform_setting')
    op.drop_index(op.f('ix_platform_setting_id'), table_name='platform_setting')
    op.drop_index(op.f('ix_platform_setting_category'), table_name='platform_setting')
    op.drop_table('platform_setting')
    op.drop_index(op.f('ix_admin_action_target_type'), table_name='admin_action')
    op.drop_index(op.f('ix_admin_action_target_id'), table_name='admin_action')
    op.drop_index(op.f('ix_admin_action_id'), table_name='admin_action')
    op.drop_index(op.f('ix_admin_action_admin_id'), table_name='admin_action')
    op.drop_index(op.f('ix_admin_action_action'), table_name='admin_action')
    op.drop_table('admin_action')
    op.drop_index(op.f('ix_admin_user_id'), table_name='admin_user')
    op.drop_index(op.f('ix_admin_user_email'), table_name='admin_user')
    op.drop_table('admin_user')