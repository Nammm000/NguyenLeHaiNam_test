"""Add tags and todo_tags tables

- tags: user-scoped labels; names unique per user case-insensitively via the
  functional index uq_tags_user_name_ci (user_id, lower(name)).
- todo_tags: association table (composite PK todo_id + tag_id), FKs cascade
  on delete so dropping a todo or tag cleans up relations automatically.

The tables are new (empty), so indexes are created non-concurrently —
CONCURRENTLY is only needed when indexing an existing populated table.

Revision ID: c8d9e0f1a2b3
Revises: b7f2e8a1c9d3
Create Date: 2026-09-19

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c8d9e0f1a2b3"
down_revision = "b7f2e8a1c9d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "todo_tags",
        sa.Column("todo_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("todo_id", "tag_id"),
    )
    op.create_index("ix_tags_user_id", "tags", ["user_id"])
    op.create_index(
        "uq_tags_user_name_ci",
        "tags",
        ["user_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index("ix_todo_tags_todo_id", "todo_tags", ["todo_id"])
    op.create_index("ix_todo_tags_tag_id", "todo_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_todo_tags_tag_id", table_name="todo_tags")
    op.drop_index("ix_todo_tags_todo_id", table_name="todo_tags")
    op.drop_index("uq_tags_user_name_ci", table_name="tags")
    op.drop_index("ix_tags_user_id", table_name="tags")
    op.drop_table("todo_tags")
    op.drop_table("tags")
