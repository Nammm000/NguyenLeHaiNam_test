"""Add unique users.email index and todo list indexes

- uq_users_email (UNIQUE): closes the duplicate-email gap (concurrent
  registrations could create two accounts with the same email; login then
  fails with MultipleResultsFound / HTTP 500).
- ix_todos_user_completed_created_at: composite index for user-scoped,
  status-filtered list queries.
- ix_todos_user_created_id: serves the default list ordering
  (created_at DESC, id DESC) without a sort node.

On PostgreSQL the indexes are built CONCURRENTLY: the table stays writable
for readers/writers during the build. CONCURRENTLY cannot run inside a
transaction (hence the autocommit block) and, if it fails, leaves an INVALID
index behind that must be dropped manually before retrying. Before building
the unique email index on a real production table, dedupe existing rows
first (the seed data is already unique).

Revision ID: b7f2e8a1c9d3
Revises: a0790c76a129
Create Date: 2026-09-19

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b7f2e8a1c9d3"
down_revision = "a0790c76a129"
branch_labels = None
depends_on = None

INDEXES = [
    ("uq_users_email", "users", ["email"], True),
    (
        "ix_todos_user_completed_created_at",
        "todos",
        ["user_id", "completed", "created_at"],
        False,
    ),
    ("ix_todos_user_created_id", "todos", ["user_id", "created_at", "id"], False),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for name, table, columns, unique in INDEXES:
                op.create_index(
                    name,
                    table,
                    columns,
                    unique=unique,
                    postgresql_concurrently=True,
                )
    else:
        for name, table, columns, unique in INDEXES:
            op.create_index(name, table, columns, unique=unique)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for name, table, _columns, _unique in INDEXES:
                op.drop_index(name, table_name=table, postgresql_concurrently=True)
    else:
        for name, table, _columns, _unique in INDEXES:
            op.drop_index(name, table_name=table)
