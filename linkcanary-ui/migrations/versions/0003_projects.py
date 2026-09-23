"""Add projects table and org/project scoping to crawls.

Creates the ``projects`` table (org-scoped, keyed by canonical domain) and adds
``org_id`` + ``project_id`` foreign keys to ``crawls`` so a series of audits of
the same site group into a project for history/diffing.

Revision ID: 0003_projects
Revises: 0002_auth
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_projects"
down_revision: Union[str, None] = "0002_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sitemap_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "domain", name="uq_project_org_domain"),
    )
    op.create_index("ix_projects_org_id", "projects", ["org_id"])
    op.create_index("ix_projects_domain", "projects", ["domain"])

    # Existing local data is dev-only → fresh Postgres start per the migration
    # spec. org_id is added NOT NULL; a non-empty dev table must be reset.
    # batch_alter_table keeps the ALTER portable across SQLite and Postgres.
    with op.batch_alter_table("crawls") as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.String(36), nullable=False))
        batch_op.add_column(sa.Column("project_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_crawls_org_id", "organizations", ["org_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_foreign_key(
            "fk_crawls_project_id", "projects", ["project_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_crawls_org_id", ["org_id"])
        batch_op.create_index("ix_crawls_project_id", ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("crawls") as batch_op:
        batch_op.drop_index("ix_crawls_project_id")
        batch_op.drop_index("ix_crawls_org_id")
        batch_op.drop_constraint("fk_crawls_project_id", type_="foreignkey")
        batch_op.drop_constraint("fk_crawls_org_id", type_="foreignkey")
        batch_op.drop_column("project_id")
        batch_op.drop_column("org_id")
    op.drop_index("ix_projects_domain", table_name="projects")
    op.drop_index("ix_projects_org_id", table_name="projects")
    op.drop_table("projects")
