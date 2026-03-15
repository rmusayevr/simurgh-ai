"""
Fixture package — re-exports all factory functions and fixtures.

Import factories directly in test files:
    from tests.fixtures.users import build_user, build_superuser
    from tests.fixtures.projects import build_project
    ...

pytest fixtures (decorated with @pytest.fixture) are automatically discovered
when this package is imported via conftest.py.
"""

from tests.fixtures.users import build_user, build_superuser, build_inactive_user
from tests.fixtures.projects import (
    build_project,
    build_project_member_link,
    build_historical_document,
)
from tests.fixtures.stakeholders import (
    build_stakeholder,
    build_key_player,
    build_keep_satisfied,
    build_keep_informed,
    build_monitor,
    build_blocker,
    build_champion,
)
from tests.fixtures.proposals import (
    build_proposal,
    build_proposal_variation,
    build_draft_proposal,
    build_approved_proposal,
    build_failed_proposal,
    build_all_persona_variations,
)
from tests.fixtures.debates import (
    build_debate_session,
    build_debate_turn,
    build_complete_debate,
    build_in_progress_debate,
    build_timed_out_debate,
)
from tests.fixtures.documents import (
    build_document,
    build_pending_document,
    build_failed_document,
    build_txt_document,
    make_upload_file,
    sample_pdf_bytes,
    sample_docx_bytes,
    sample_txt_bytes,
)

__all__ = [
    "build_user",
    "build_superuser",
    "build_inactive_user",
    "build_project",
    "build_project_member_link",
    "build_historical_document",
    "build_stakeholder",
    "build_key_player",
    "build_keep_satisfied",
    "build_keep_informed",
    "build_monitor",
    "build_blocker",
    "build_champion",
    "build_proposal",
    "build_proposal_variation",
    "build_draft_proposal",
    "build_approved_proposal",
    "build_failed_proposal",
    "build_all_persona_variations",
    "build_debate_session",
    "build_debate_turn",
    "build_complete_debate",
    "build_in_progress_debate",
    "build_timed_out_debate",
    "build_document",
    "build_pending_document",
    "build_failed_document",
    "build_txt_document",
    "make_upload_file",
    "sample_pdf_bytes",
    "sample_docx_bytes",
    "sample_txt_bytes",
]
