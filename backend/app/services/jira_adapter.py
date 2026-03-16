"""
Jira adapter service.

Exports Simurgh AI proposals to Jira as epics with child stories.

Credential resolution order:
    1. User's stored Atlassian OAuth credential (AtlassianCredential table)
       — zero setup for users who logged in via Atlassian
    2. Environment variable API token fallback
       (JIRA_DEFAULT_INSTANCE_URL + JIRA_DEFAULT_USER_EMAIL + JIRA_DEFAULT_API_TOKEN)
       — for users who authenticated via email/GitHub/Google

The exported structure:
    Epic  ← proposal title / task description
      Story: Architecture Overview     ← executive summary from PRD
      Story: Technical Approach        ← core architecture section
      Story: Risks & Trade-offs        ← risks from PRD
      Story: Implementation Timeline   ← timeline section if present
"""

import re
import httpx
import structlog
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.models.proposal import Proposal, ProposalVariation
from app.models.atlassian_credential import AtlassianCredential
from app.services.atlassian_oauth_service import AtlassianOAuthService

logger = structlog.get_logger(__name__)


class JiraAdapter:
    """
    Exports proposals to Jira using the best available credentials.

    Instantiate per-request with the current user_id so credential
    resolution is user-scoped.
    """

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    # ── Credential resolution ─────────────────────────────────────────────────

    async def _get_auth_headers(self) -> tuple[dict, str]:
        """
        Resolve auth headers and base URL from the best available source.

        Returns:
            tuple[dict, str]: (headers dict, base_url)

        Raises:
            BadRequestException: If no credentials are available
        """
        # 1. Try stored Atlassian OAuth credential
        oauth_service = AtlassianOAuthService(self.db)
        access_token = await oauth_service.get_valid_access_token(self.user_id)

        if access_token:
            result = await self.db.exec(
                select(AtlassianCredential).where(
                    AtlassianCredential.user_id == self.user_id
                )
            )
            cred = result.first()
            if cred:
                return (
                    {
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "X-Atlassian-Token": "no-check",
                    },
                    f"https://api.atlassian.com/ex/jira/{cred.cloud_id}/rest/api/3",
                )

        # No credential available
        raise BadRequestException(
            "No Jira credentials available. Connect your Atlassian account in "
            "Settings → Integrations to enable Jira export."
        )

    # ── Project key validation ─────────────────────────────────────────────────

    async def validate_project_key(self, project_key: str) -> dict:
        """
        Check that a Jira project key exists and is accessible.

        Args:
            project_key: e.g. "PROJ"

        Returns:
            dict: Jira project info (id, key, name, issue types)

        Raises:
            BadRequestException: If project not found or not accessible
        """
        headers, base_url = await self._get_auth_headers()
        project_key = project_key.upper().strip()

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{base_url}/project/{project_key}",
                headers=headers,
            )

        if res.status_code == 404:
            raise BadRequestException(
                f"Jira project '{project_key}' not found. "
                "Check the project key and make sure you have access to it."
            )
        if res.status_code == 401:
            raise UnauthorizedException(
                "Jira authentication failed. Please reconnect your Atlassian account."
            )
        if not res.is_success:
            raise BadRequestException(
                f"Failed to validate Jira project: {res.text[:200]}"
            )

        return res.json()

    # ── Issue type resolution ─────────────────────────────────────────────────

    async def _get_issue_type_id(
        self, base_url: str, headers: dict, project_key: str, type_name: str
    ) -> Optional[str]:
        """
        Get the issue type ID for a given type name in a project.
        Falls back gracefully if the type doesn't exist.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{base_url}/issue/createmeta/{project_key}/issuetypes",
                headers=headers,
            )

        if not res.is_success:
            return None

        issue_types = res.json().get("issueTypes", [])
        # Case-insensitive match
        for it in issue_types:
            if it.get("name", "").lower() == type_name.lower():
                return it["id"]

        # Common fallback names
        fallbacks = {
            "epic": ["Epic", "Feature"],
            "story": ["Story", "Task", "Sub-task"],
        }
        for fallback in fallbacks.get(type_name.lower(), []):
            for it in issue_types:
                if it.get("name", "").lower() == fallback.lower():
                    return it["id"]

        # Last resort: return the first available type
        return issue_types[0]["id"] if issue_types else None

    # ── PRD section extraction ────────────────────────────────────────────────

    def _extract_prd_sections(self, prd_markdown: str) -> dict:
        """
        Extract named sections from the PRD markdown for use in Jira stories.

        Returns a dict with keys: overview, approach, risks, timeline.
        Each value is a plain-text snippet (≤500 chars) suitable for a
        Jira story description.
        """
        sections = {
            "overview": "",
            "approach": "",
            "risks": "",
            "timeline": "",
        }

        # Split on markdown headings
        parts = re.split(r"\n#{1,3}\s+", prd_markdown)

        heading_map = {
            "overview": ["executive summary", "overview", "summary"],
            "approach": [
                "technical approach",
                "architecture",
                "approach",
                "solution",
                "design",
            ],
            "risks": [
                "risks",
                "trade-offs",
                "tradeoffs",
                "trade offs",
                "risks & trade",
            ],
            "timeline": ["timeline", "implementation", "roadmap", "phases"],
        }

        for part in parts:
            first_line = part.split("\n")[0].lower().strip()
            body = "\n".join(part.split("\n")[1:]).strip()

            for key, keywords in heading_map.items():
                if any(kw in first_line for kw in keywords):
                    if not sections[key]:  # Take the first match
                        # Strip markdown, truncate
                        clean = re.sub(r"[*_`#\[\]()]", "", body)
                        clean = re.sub(r"\n+", " ", clean).strip()
                        sections[key] = clean[:500]

        # Fallback: use first 500 chars of PRD as overview
        if not sections["overview"]:
            clean = re.sub(r"[*_`#\[\]()]", "", prd_markdown)
            clean = re.sub(r"\n+", " ", clean).strip()
            sections["overview"] = clean[:500]

        return sections

    # ── Main export ───────────────────────────────────────────────────────────

    async def export_proposal(
        self,
        proposal: Proposal,
        variation: ProposalVariation,
        jira_project_key: str,
    ) -> dict:
        """
        Export a proposal variation to Jira as an epic with child stories.

        Creates:
            1. An Epic with the proposal's task description as title
            2. Up to 4 Story issues linked to the epic:
               - Architecture Overview
               - Technical Approach
               - Risks & Trade-offs
               - Implementation Timeline (if found in PRD)

        Args:
            proposal:         The parent Proposal
            variation:        The selected ProposalVariation to export
            jira_project_key: Target Jira project key (e.g. "PROJ")

        Returns:
            dict with: epic_key, epic_url, stories (list of {key, url, title})
        """
        headers, base_url = await self._get_auth_headers()
        project_key = jira_project_key.upper().strip()

        # Validate project exists first
        await self.validate_project_key(project_key)

        # Resolve issue type IDs
        epic_type_id = await self._get_issue_type_id(
            base_url, headers, project_key, "epic"
        )
        story_type_id = await self._get_issue_type_id(
            base_url, headers, project_key, "story"
        )

        persona_name = variation.agent_persona.value.replace("_", " ").title()
        epic_title = (
            f"[Simurgh AI] {proposal.task_description[:80]}"
            if len(proposal.task_description) > 80
            else f"[Simurgh AI] {proposal.task_description}"
        )

        sections = self._extract_prd_sections(variation.structured_prd)

        # ── 1. Create the Epic ────────────────────────────────────────────────
        epic_body = {
            "fields": {
                "project": {"key": project_key},
                "summary": epic_title,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        f"Generated by Simurgh AI — {persona_name} persona.\n\n"
                                        f"Task: {proposal.task_description}\n\n"
                                        f"Confidence: {variation.confidence_score}%"
                                    ),
                                }
                            ],
                        }
                    ],
                },
                "issuetype": {"id": epic_type_id} if epic_type_id else {"name": "Epic"},
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            epic_res = await client.post(
                f"{base_url}/issue",
                headers=headers,
                json=epic_body,
            )

        if not epic_res.is_success:
            logger.error(
                "jira_epic_creation_failed",
                status=epic_res.status_code,
                body=epic_res.text[:300],
            )
            raise BadRequestException(
                f"Failed to create Jira epic: {epic_res.text[:200]}"
            )

        epic_data = epic_res.json()
        epic_key = epic_data["key"]
        # Build browse URL from site_url (not the API base URL)
        result_cred = await self.db.exec(
            select(AtlassianCredential).where(
                AtlassianCredential.user_id == self.user_id
            )
        )
        _cred = result_cred.first()
        _site = _cred.site_url if _cred else base_url.replace("/rest/api/3", "")
        epic_url = f"{_site}/browse/{epic_key}"

        # ── 2. Create child Stories ───────────────────────────────────────────
        stories_to_create = [
            ("Architecture Overview", sections["overview"]),
            ("Technical Approach", sections["approach"]),
            ("Risks & Trade-offs", sections["risks"]),
        ]
        if sections["timeline"]:
            stories_to_create.append(("Implementation Timeline", sections["timeline"]))

        created_stories = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            for story_title, story_body in stories_to_create:
                story_payload = {
                    "fields": {
                        "project": {"key": project_key},
                        "summary": f"{epic_key}: {story_title}",
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": story_body
                                            or f"See epic {epic_key} for details.",
                                        }
                                    ],
                                }
                            ],
                        },
                        "issuetype": (
                            {"id": story_type_id}
                            if story_type_id
                            else {"name": "Story"}
                        ),
                    }
                }

                # Link to epic if the project supports it
                try:
                    story_payload["fields"]["customfield_10014"] = epic_key  # Epic Link
                except Exception:
                    pass

                story_res = await client.post(
                    f"{base_url}/issue",
                    headers=headers,
                    json=story_payload,
                )

                if story_res.is_success:
                    story_data = story_res.json()
                    story_key = story_data["key"]
                    created_stories.append(
                        {
                            "key": story_key,
                            "url": f"{_site}/browse/{story_key}",
                            "title": story_title,
                        }
                    )
                else:
                    logger.warning(
                        "jira_story_creation_failed",
                        story_title=story_title,
                        status=story_res.status_code,
                    )

        # ── 3. Persist epic key on the proposal ──────────────────────────────
        proposal.jira_epic_key = epic_key
        proposal.jira_epic_url = epic_url
        proposal.jira_project_key = project_key
        proposal.jira_exported_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(proposal)
        await self.db.commit()

        logger.info(
            "jira_export_completed",
            proposal_id=proposal.id,
            epic_key=epic_key,
            stories_created=len(created_stories),
        )

        return {
            "epic_key": epic_key,
            "epic_url": epic_url,
            "project_key": project_key,
            "stories": created_stories,
        }
