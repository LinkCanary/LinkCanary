"""Add check_core_web_vitals flag to crawls.

Revision ID: 0004_core_web_vitals
Revises: 0003_projects
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_core_web_vitals"
down_revision: Union[str, None] = "0003_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crawls", sa.Column("check_core_web_vitals", sa.Boolean, server_default="false"))


def downgrade() -> None:
    op.drop_column("crawls", "check_core_web_vitals")
