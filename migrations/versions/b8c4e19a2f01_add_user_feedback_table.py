"""add user_feedback table"""
from alembic import op
import sqlalchemy as sa

revision = "b8c4e19a2f01"
down_revision = "a5d052ee0477"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("experience_rating", sa.SmallInteger(), nullable=False),
        sa.Column("ease_of_use", sa.SmallInteger(), nullable=False),
        sa.Column("insightfulness", sa.SmallInteger(), nullable=False),
        sa.Column("most_valuable_aspect", sa.String(length=64), nullable=False),
        sa.Column("would_recommend", sa.Boolean(), nullable=False),
        sa.Column("improvement_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("experience_rating BETWEEN 1 AND 10", name="ck_feedback_experience_range"),
        sa.CheckConstraint("ease_of_use BETWEEN 1 AND 5", name="ck_feedback_ease_range"),
        sa.CheckConstraint("insightfulness BETWEEN 1 AND 5", name="ck_feedback_insight_range"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_feedback_created_at"), "user_feedback", ["created_at"], unique=False)
    op.create_index(op.f("ix_user_feedback_user_id"), "user_feedback", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_user_feedback_user_id"), table_name="user_feedback")
    op.drop_index(op.f("ix_user_feedback_created_at"), table_name="user_feedback")
    op.drop_table("user_feedback")
