"""create recommendation tables

Revision ID: 001
Revises:
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tutor_metrics",
        sa.Column("tutor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("average_rating", sa.Float(), nullable=False),
        sa.Column("total_reviews", sa.Integer(), nullable=False),
        sa.Column("total_sessions", sa.Integer(), nullable=False),
        sa.Column("sessions_completed", sa.Integer(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("subjects", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("activity_score", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("recommendation_score", sa.Float(), nullable=False),
        sa.Column("last_activity", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("tutor_id"),
    )
    op.create_index("ix_tutor_metrics_recommendation_score", "tutor_metrics", ["recommendation_score"], unique=False)

    op.create_table(
        "recommendation_scores",
        sa.Column("tutor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("tutor_id", "subject"),
    )
    op.create_index("ix_recommendation_scores_subject", "recommendation_scores", ["subject"], unique=False)
    op.create_index("ix_recommendation_scores_score", "recommendation_scores", ["score"], unique=False)

    op.create_table(
        "trending_tutors",
        sa.Column("tutor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("growth_rate", sa.Float(), nullable=False),
        sa.Column("trend_score", sa.Float(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("tutor_id"),
    )
    op.create_index("ix_trending_tutors_trend_score", "trending_tutors", ["trend_score"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trending_tutors_trend_score", table_name="trending_tutors")
    op.drop_table("trending_tutors")
    op.drop_index("ix_recommendation_scores_score", table_name="recommendation_scores")
    op.drop_index("ix_recommendation_scores_subject", table_name="recommendation_scores")
    op.drop_table("recommendation_scores")
    op.drop_index("ix_tutor_metrics_recommendation_score", table_name="tutor_metrics")
    op.drop_table("tutor_metrics")
