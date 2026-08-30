"""initial tables

Revision ID: 001_initial_tables
Revises: 
Create Date: 2026-08-22 10:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = '001_initial_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Users Table ──
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'operator', name='user_role'), nullable=False, server_default='operator'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 2. Vendors Table ──
    op.create_table(
        'vendors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('site_name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 3. Golden References Table ──
    op.create_table(
        'golden_references',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('part_id', sa.String(100), nullable=False, index=True),
        sa.Column('part_name', sa.String(255), nullable=False),
        sa.Column('image_path', sa.String(512), nullable=False),
        sa.Column('thumbnail_path', sa.String(512), nullable=True),
        sa.Column('embedding_id', sa.String(100), nullable=True, index=True),
        sa.Column('roi_template_path', sa.String(512), nullable=True),
        sa.Column('view_angle', sa.String(50), nullable=False, server_default='front'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 4. Inspections Table ──
    op.create_table(
        'inspections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_number', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('location', sa.String(255), nullable=False, index=True),
        sa.Column('golden_reference_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('golden_references.id', ondelete='SET NULL'), nullable=True),
        sa.Column('image_paths', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('image_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('quality_passed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('quality_failure_reason', sa.String(500), nullable=True),
        sa.Column('authenticity_score', sa.Float(), nullable=True),
        sa.Column('authenticity_flagged', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('reference_similarity', sa.Float(), nullable=True),
        sa.Column('fraud_probability', sa.Float(), nullable=True),
        sa.Column('judge_confidence', sa.Float(), nullable=True),
        sa.Column('fraud_category', sa.String(100), nullable=True, index=True),
        sa.Column('root_cause', sa.String(4000), nullable=True),
        sa.Column('verdict', sa.Enum('accept', 'reject', 'review', 'pending', name='inspection_verdict'), nullable=False, server_default='pending', index=True),
        sa.Column('policy_action', sa.Enum('accept', 'retake', 'quarantine', 'vendor_verification', name='policy_action'), nullable=True, index=True),
        sa.Column('report_path', sa.String(500), nullable=True),
        sa.Column('review_decision', sa.Enum('approved', 'overridden', 'pending', name='review_decision'), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewer_comment', sa.String(2000), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('working_memory', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 5. Evidence Table ──
    op.create_table(
        'evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('inspection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inspections.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('agent_type', sa.Enum('ocr', 'label', 'structural', 'vlm', name='agent_type'), nullable=False, index=True),
        sa.Column('detector_name', sa.String(100), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('roi_id', sa.String(100), nullable=False),
        sa.Column('roi_type', sa.String(50), nullable=False),
        sa.Column('bounding_box', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('detected_count', sa.Integer(), nullable=True),
        sa.Column('expected_count', sa.Integer(), nullable=True),
        sa.Column('component_findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence_summary', sa.String(2000), nullable=False),
        sa.Column('explanation', sa.String(2000), nullable=False),
        sa.Column('raw_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=False),
        sa.Column('failed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('failure_reason', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('evidence')
    op.drop_table('inspections')
    op.drop_table('golden_references')
    op.drop_table('vendors')
    op.drop_table('users')
    op.execute('DROP TYPE IF EXISTS agent_type')
    op.execute('DROP TYPE IF EXISTS review_decision')
    op.execute('DROP TYPE IF EXISTS policy_action')
    op.execute('DROP TYPE IF EXISTS inspection_verdict')
    op.execute('DROP TYPE IF EXISTS user_role')
