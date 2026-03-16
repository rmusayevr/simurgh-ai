"""
Confluence adapter service.

Exports Simurgh AI proposals to Confluence as structured pages.

Three audience-specific export presets:

    INTERNAL_TECH_REVIEW
        Full content — architecture, risks, sentiment analysis,
        debate transcript summary, trade-offs, confidence scores.
        Audience: Engineering team, Tech Leads, Architects.

    EXECUTIVE_PRESENTATION
        Concise — executive summary, risks overview, budget/timeline.
        Strips sentiment data, persona debate, and technical detail.
        Audience: CTO, VP Engineering, Product leadership.

    PUBLIC_DOCUMENTATION
        Architecture only — clean technical spec with no internal data.
        Strips all sensitive content: sentiment, budget, approval chain.
        Audience: External teams, vendors, public wiki.

Credential resolution order:
    1. User's stored Atlassian OAuth credential (zero setup for Atlassian users)
    2. JIRA_DEFAULT_* env vars (Confluence shares the same Atlassian site)
"""

import re
import httpx
import structlog
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.models.proposal import Proposal, ProposalVariation
from app.models.atlassian_credential import AtlassianCredential
from app.services.atlassian_oauth_service import AtlassianOAuthService

logger = structlog.get_logger(__name__)


class ExportPreset(str, Enum):
    INTERNAL_TECH_REVIEW = "internal_tech_review"
    EXECUTIVE_PRESENTATION = "executive_presentation"
    PUBLIC_DOCUMENTATION = "public_documentation"


PRESET_LABELS = {
    ExportPreset.INTERNAL_TECH_REVIEW: "Internal Tech Review",
    ExportPreset.EXECUTIVE_PRESENTATION: "Executive Presentation",
    ExportPreset.PUBLIC_DOCUMENTATION: "Public Documentation",
}


class ConfluenceAdapter:
    """
    Exports proposals to Confluence using the best available credentials.
    """

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    # ── Credential resolution ─────────────────────────────────────────────────

    async def _get_auth_headers(self) -> tuple[dict, str]:
        """
        Resolve auth headers and Confluence base URL.

        Returns:
            tuple[dict, str]: (headers, confluence_base_url)
        """
        oauth_service = AtlassianOAuthService(self.db)
        access_token = await oauth_service.get_valid_access_token(self.user_id)

        logger.debug(
            "confluence_auth_debug",
            user_id=self.user_id,
            has_token=access_token is not None,
            token_prefix=access_token[:20] if access_token else None,
        )

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
                    f"https://api.atlassian.com/ex/confluence/{cred.cloud_id}",
                )

        # No credential available
        raise BadRequestException(
            "No Confluence credentials available. Connect your Atlassian account in "
            "Settings → Integrations to enable Confluence export."
        )

    # ── Space validation ──────────────────────────────────────────────────────

    async def validate_space(self, space_key: str) -> dict:
        """
        Verify a Confluence space exists and is accessible using the v2 API.
        """
        headers, base_url = await self._get_auth_headers()
        space_key = space_key.upper().strip()

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{base_url}/wiki/api/v2/spaces",
                headers={**headers, "X-Atlassian-Token": "no-check"},
                params={"keys": space_key, "limit": 1},
            )

        if res.status_code == 401:
            raise UnauthorizedException(
                f"Confluence authentication failed (401): {res.text[:300]}"
            )
        if res.status_code == 403:
            raise BadRequestException(
                f"Confluence access denied (403): {res.text[:300]}"
            )
        if not res.is_success:
            raise BadRequestException(
                f"Failed to validate Confluence space: {res.text[:200]}"
            )

        data = res.json()
        results = data.get("results", [])
        if not results:
            raise BadRequestException(
                f"Confluence space '{space_key}' not found. "
                "Check the space key and make sure you have access to it."
            )

        return results[0]

    # ── PRD section extraction ────────────────────────────────────────────────

    def _extract_sections(self, prd_markdown: str) -> dict:
        """
        Extract named sections from PRD markdown.

        Returns dict with keys: overview, architecture, risks, timeline,
        tech_stack, trade_offs — each as cleaned plain text.
        """
        sections: dict = {
            "overview": "",
            "architecture": "",
            "risks": "",
            "timeline": "",
            "tech_stack": "",
            "trade_offs": "",
        }

        parts = re.split(r"\n#{1,3}\s+", prd_markdown)

        heading_map = {
            "overview": ["executive summary", "overview", "summary", "introduction"],
            "architecture": [
                "architecture",
                "technical approach",
                "solution design",
                "design",
                "approach",
            ],
            "risks": ["risk", "trade-off", "tradeoff", "concern"],
            "timeline": ["timeline", "implementation", "roadmap", "phase", "schedule"],
            "tech_stack": ["tech stack", "technology", "stack", "tools", "frameworks"],
            "trade_offs": ["trade-off", "tradeoff", "pros and cons", "considerations"],
        }

        for part in parts:
            lines = part.split("\n")
            first_line = lines[0].lower().strip()
            body = "\n".join(lines[1:]).strip()

            for key, keywords in heading_map.items():
                if any(kw in first_line for kw in keywords):
                    if not sections[key]:
                        sections[key] = body

        if not sections["overview"] and prd_markdown:
            sections["overview"] = prd_markdown[:800]

        return sections

    # ── Content builders per preset ───────────────────────────────────────────

    def _build_storage_format(
        self,
        proposal: Proposal,
        variation: ProposalVariation,
        preset: ExportPreset,
        sections: dict,
    ) -> str:
        """
        Build the Confluence Storage Format (XHTML) body for the page.

        Each preset includes/excludes different content sections.
        """
        persona_name = variation.agent_persona.value.replace("_", " ").title()
        task = proposal.task_description
        confidence = variation.confidence_score

        def _p(text: str) -> str:
            """Wrap text in a paragraph tag, escaping special chars."""
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return f"<p>{safe}</p>"

        def _section(title: str, body: str) -> str:
            if not body.strip():
                return ""
            safe_body = (
                body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            # Preserve line breaks
            formatted = safe_body.replace("\n\n", "</p><p>").replace("\n", "<br/>")
            return f"<h2>{title}</h2><p>{formatted}</p>"

        def _info_panel(text: str) -> str:
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return (
                f'<ac:structured-macro ac:name="info">'
                f"<ac:rich-text-body><p>{safe}</p></ac:rich-text-body>"
                f"</ac:structured-macro>"
            )

        def _note_panel(text: str) -> str:
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return (
                f'<ac:structured-macro ac:name="note">'
                f"<ac:rich-text-body><p>{safe}</p></ac:rich-text-body>"
                f"</ac:structured-macro>"
            )

        # ── Header block (all presets) ────────────────────────────────────────
        header = _info_panel(
            f"Generated by Simurgh AI | Persona: {persona_name} | "
            f"Confidence: {confidence}%"
        )

        if preset == ExportPreset.PUBLIC_DOCUMENTATION:
            # Architecture only — no persona, confidence, sentiment, or debate
            body = (
                "<h1>Architecture Specification</h1>"
                + _p(task)
                + _section("Overview", sections["overview"])
                + _section("Architecture", sections["architecture"])
                + _section("Technology Stack", sections["tech_stack"])
                + _section("Implementation Timeline", sections["timeline"])
            )
            return body

        if preset == ExportPreset.EXECUTIVE_PRESENTATION:
            # Executive summary + risks + timeline only
            body = (
                "<h1>Architecture Proposal — Executive Summary</h1>"
                + header
                + _p(f"Task: {task}")
                + _section("Executive Summary", sections["overview"])
                + _section("Key Risks", sections["risks"])
                + _section("Implementation Timeline", sections["timeline"])
                + _note_panel(
                    "Full technical detail available in the Internal Tech Review version."
                )
            )
            return body

        # INTERNAL_TECH_REVIEW — full content
        approval_info = ""
        if proposal.approved_at and proposal.approval_status.value == "APPROVED":
            approval_info = _info_panel(
                f"Status: APPROVED | Approved at: {proposal.approved_at.strftime('%Y-%m-%d %H:%M UTC')}"
            )

        jira_link = ""
        if proposal.jira_epic_key and proposal.jira_epic_url:
            jira_link = (
                f'<p>Jira Epic: <a href="{proposal.jira_epic_url}">'
                f"{proposal.jira_epic_key}</a></p>"
            )

        body = (
            "<h1>Architecture Proposal — Internal Tech Review</h1>"
            + header
            + approval_info
            + _p(f"Task: {task}")
            + jira_link
            + _section("Executive Summary", sections["overview"])
            + _section("Architecture & Technical Approach", sections["architecture"])
            + _section("Technology Stack", sections["tech_stack"])
            + _section("Trade-offs", sections["trade_offs"] or sections["risks"])
            + _section("Risks", sections["risks"])
            + _section("Implementation Timeline", sections["timeline"])
        )

        # Append reasoning and trade-offs from variation
        if variation.reasoning:
            safe_reasoning = (
                variation.reasoning.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            body += f"<h2>{persona_name} — Reasoning</h2><p>{safe_reasoning}</p>"

        if variation.trade_offs:
            safe_tradeoffs = (
                variation.trade_offs.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            body += f"<h2>Identified Trade-offs</h2><p>{safe_tradeoffs}</p>"

        return body

    # ── Main export ───────────────────────────────────────────────────────────

    async def export_proposal(
        self,
        proposal: Proposal,
        variation: ProposalVariation,
        space_key: str,
        preset: ExportPreset,
        parent_page_id: Optional[str] = None,
    ) -> dict:
        """
        Export a proposal variation to Confluence as a page.

        Args:
            proposal:       The parent Proposal
            variation:      The selected ProposalVariation
            space_key:      Target Confluence space key (e.g. "ARCH")
            preset:         Export preset controlling content depth
            parent_page_id: Optional parent page ID to nest under

        Returns:
            dict with: page_id, page_url, title, preset
        """
        headers, base_url = await self._get_auth_headers()
        space_key = space_key.upper().strip()

        # Validate space exists
        await self.validate_space(space_key)

        persona_name = variation.agent_persona.value.replace("_", " ").title()
        preset_label = PRESET_LABELS[preset]

        page_title = (
            f"[Simurgh AI] {proposal.task_description[:60]} "
            f"— {preset_label} ({persona_name})"
        )

        sections = self._extract_sections(variation.structured_prd)
        body_storage = self._build_storage_format(proposal, variation, preset, sections)

        page_payload: dict = {
            "type": "page",
            "title": page_title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body_storage,
                    "representation": "storage",
                }
            },
        }

        if parent_page_id:
            page_payload["ancestors"] = [{"id": parent_page_id}]

        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                f"{base_url}/wiki/rest/api/content",
                headers=headers,
                json=page_payload,
            )

        if not res.is_success:
            logger.error(
                "confluence_page_creation_failed",
                status=res.status_code,
                body=res.text[:300],
            )
            raise BadRequestException(
                f"Failed to create Confluence page: {res.text[:200]}"
            )

        page_data = res.json()
        page_id = page_data["id"]

        # Build the view URL using site_url from credential
        result = await self.db.exec(
            select(AtlassianCredential).where(
                AtlassianCredential.user_id == self.user_id
            )
        )
        cred = result.first()
        site_url = (
            cred.site_url
            if cred
            else base_url.replace(
                f"https://api.atlassian.com/ex/confluence/{cred.cloud_id if cred else ''}/rest/api",
                "",
            )
        )
        webui_path = page_data.get("_links", {}).get(
            "webui", f"/spaces/{space_key}/pages/{page_id}"
        )
        page_url = (
            f"{site_url}/wiki{webui_path}"
            if not webui_path.startswith("http")
            else webui_path
        )

        # Persist on proposal
        proposal.confluence_page_id = page_id
        proposal.confluence_page_url = page_url
        proposal.confluence_space_key = space_key
        proposal.confluence_exported_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        )
        self.db.add(proposal)
        await self.db.commit()

        logger.info(
            "confluence_export_completed",
            proposal_id=proposal.id,
            page_id=page_id,
            preset=preset.value,
        )

        return {
            "page_id": page_id,
            "page_url": page_url,
            "title": page_title,
            "preset": preset.value,
            "space_key": space_key,
        }
