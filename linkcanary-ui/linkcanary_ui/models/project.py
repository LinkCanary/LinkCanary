"""Project model — groups crawls of the same site over time.

A project is the stable identity a series of crawls attach to, which is what
makes "what changed since the last audit" expressible. Projects are org-scoped
and keyed by a canonical domain so a manual crawl and a CI-triggered crawl of
the same site both resolve to the same project automatically.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("org_id", "domain", name="uq_project_org_domain"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Canonical grouping key: normalized domain (netloc, lowercased, no www.).
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Human-editable display name; defaults to the domain on creation.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # First sitemap URL that created the project, kept as a reference point.
    sitemap_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    crawls: Mapped[list["Crawl"]] = relationship(back_populates="project")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "name": self.name,
            "sitemap_url": self.sitemap_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
