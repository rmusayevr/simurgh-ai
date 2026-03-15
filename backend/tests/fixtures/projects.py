"""
Project factory fixtures.

Provides in-memory Project and ProjectStakeholderLink instances.
Not persisted — use seed_minimal() for integration tests.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.models.project import (
    Project,
    ProjectVisibility,
    HistoricalDocument,
    DocumentStatus,
)
from app.models.links import ProjectStakeholderLink, ProjectRole


# ── Low-level factories ────────────────────────────────────────────────────────


def build_project(
    id: int = 1,
    name: str = "Test Project",
    description: str = "A project for testing purposes",
    owner_id: int = 1,
    visibility: ProjectVisibility = ProjectVisibility.PRIVATE,
    is_archived: bool = False,
    tags: str | None = "test,backend",
    tech_stack: str | None = "Python,FastAPI,PostgreSQL",
    document_count: int = 0,
    proposal_count: int = 0,
    member_count: int = 0,
) -> Project:
    """
    Build an in-memory Project with sensible defaults.

    Args:
        id:             Simulated PK
        name:           Project name
        description:    Optional description
        owner_id:       FK to the owning User
        visibility:     ProjectVisibility level
        is_archived:    Soft-delete flag
        tags:           Comma-separated tags
        tech_stack:     Comma-separated technologies
        document_count: Cached document count
        proposal_count: Cached proposal count
        member_count:   Cached member count

    Returns:
        Project: Unsaved instance
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return Project(
        id=id,
        name=name,
        description=description,
        owner_id=owner_id,
        visibility=visibility,
        is_archived=is_archived,
        tags=tags,
        tech_stack=tech_stack,
        document_count=document_count,
        proposal_count=proposal_count,
        member_count=member_count,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
    )


def build_project_member_link(
    project_id: int = 1,
    user_id: int = 2,
    role: ProjectRole = ProjectRole.EDITOR,
    added_by_id: int | None = 1,
) -> ProjectStakeholderLink:
    """
    Build an in-memory ProjectStakeholderLink (project membership row).

    Args:
        project_id:   FK to Project
        user_id:      FK to User being added
        role:         ProjectRole for this membership
        added_by_id:  FK to User who added this member

    Returns:
        ProjectStakeholderLink: Unsaved instance
    """
    return ProjectStakeholderLink(
        project_id=project_id,
        user_id=user_id,
        role=role,
        added_by_id=added_by_id,
        joined_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


def build_historical_document(
    id: int = 1,
    filename: str = "architecture_spec.pdf",
    project_id: int = 1,
    uploaded_by_id: int | None = 1,
    status: DocumentStatus = DocumentStatus.COMPLETED,
    content_text: str | None = "Sample architecture document content for RAG.",
    file_size_bytes: int = 204_800,
    mime_type: str = "application/pdf",
    chunk_count: int = 5,
) -> HistoricalDocument:
    """
    Build an in-memory HistoricalDocument (uploaded + processed state by default).
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return HistoricalDocument(
        id=id,
        filename=filename,
        project_id=project_id,
        uploaded_by_id=uploaded_by_id,
        status=status,
        content_text=content_text,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
        chunk_count=chunk_count,
        character_count=len(content_text) if content_text else 0,
        upload_date=now,
        processed_at=now if status == DocumentStatus.COMPLETED else None,
    )


# ── pytest fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def test_project() -> Project:
    """
    Standard private project owned by user id=1.

    Usage:
        def test_something(test_project):
            assert test_project.owner_id == 1
    """
    return build_project()


@pytest.fixture
def test_archived_project() -> Project:
    """Archived project for soft-delete tests."""
    p = build_project(id=2, name="Archived Project", is_archived=True)
    p.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return p


@pytest.fixture
def test_project_with_member(test_project) -> tuple[Project, ProjectStakeholderLink]:
    """
    Project + one member link (user_id=2, EDITOR role).

    Returns:
        tuple: (project, link)

    Usage:
        def test_membership(test_project_with_member):
            project, link = test_project_with_member
    """
    link = build_project_member_link(project_id=test_project.id, user_id=2)
    return test_project, link


@pytest.fixture
def test_document() -> HistoricalDocument:
    """
    Completed historical document for RAG tests.
    """
    return build_historical_document()


@pytest.fixture
def make_project():
    """
    Parameterizable project factory.

    Usage:
        def test_multi_project(make_project):
            p1 = make_project(id=1, name="Alpha")
            p2 = make_project(id=2, name="Beta", owner_id=5)
    """
    return build_project


@pytest.fixture
def make_project_member():
    """
    Parameterizable membership link factory.

    Usage:
        def test_roles(make_project_member):
            viewer = make_project_member(user_id=3, role=ProjectRole.VIEWER)
    """
    return build_project_member_link
