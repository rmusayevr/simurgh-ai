"""
Proposal generation service for Council of Agents workflow.

Provides:
    - Three proposal generation from council debate
    - Single persona variation generation
    - Council of Agents parallel generation

Uses DebateService for structured, turn-by-turn debate that persists
each turn to the database in real time — enabling the live transcript
UI in the War Room.
"""

import asyncio
import structlog
from typing import Any, Dict, List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.prompt import PromptTemplate

logger = structlog.get_logger()


class ProposalGenerationService:
    """
    Service for generating architectural proposals from AI agents.

    Uses composition to access base AI generation methods.
    """

    def __init__(self):
        from app.services.ai.base import ai_service

        self._ai_service = ai_service

    async def generate_three_proposals(
        self,
        session: AsyncSession,
        task: str,
        context_chunks: List[str],
        task_docs: List[str],
        stakeholders: List[Dict[str, str]],
        model: Optional[str] = None,
        use_caching: bool = True,
        proposal_id: Optional[int] = None,
        acting_user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate 3 DISTINCT proposals from Council of Agents debate.

        Phase 1: Conduct debate via DebateService (persists each turn to DB
                 in real time so the War Room live transcript works).
        Phase 2: Each persona generates THEIR OWN proposal using the debate
                 transcript as context.
        Phase 3: Return 3 separate proposals for human evaluation.

        Args:
            session: Async DB session
            task: Architectural task description
            context_chunks: RAG context chunks from project documents
            task_docs: Task-specific document texts
            stakeholders: Stakeholder profiles for context
            model: Claude model to use
            use_caching: Whether to use prompt caching
            proposal_id: Proposal ID — required for DebateService to create
                         the DebateSession row. Falls back to legacy inline
                         debate if not provided.
            acting_user_id: User ID who triggered generation — used by
                            DebateService for access control. Falls back to
                            legacy inline debate if not provided.
        """
        logger.info("three_proposals_generation_started", task_length=len(task))

        context_text = (
            "\n".join([f"- {c}" for c in context_chunks])
            if context_chunks
            else "No context available"
        )
        task_docs_text = (
            "\n".join([f"- {d}" for d in task_docs])
            if task_docs
            else "No task documents provided"
        )
        stakeholder_text = (
            "\n".join(
                [
                    f"- {s['name']} ({s['role']}): {s.get('concerns', 'N/A')}"
                    for s in stakeholders
                ]
            )
            if stakeholders
            else "No stakeholders defined"
        )

        logger.info(
            "stakeholder_context_injected",
            stakeholder_count=len(stakeholders),
            stakeholder_text_chars=len(stakeholder_text),
            is_empty=stakeholders == [],
            preview=stakeholder_text[:200] if stakeholders else None,
        )

        # ── Phase 1: Conduct debate ────────────────────────────────────────────
        # Use DebateService when we have a proposal_id so each turn is
        # committed to the database individually — enabling the live
        # transcript UI. Fall back to the legacy inline approach otherwise
        # (e.g. unit tests or callers that don't pass proposal_id).
        if proposal_id is not None and acting_user_id is not None:
            debate_result = await self._conduct_debate_via_service(
                session=session,
                proposal_id=proposal_id,
                acting_user_id=acting_user_id,
            )
        else:
            logger.warning(
                "debate_falling_back_to_inline",
                reason="proposal_id or acting_user_id not provided",
            )
            debate_result = await self._conduct_debate_inline(
                task=task,
                context_text=context_text,
                task_docs_text=task_docs_text,
                stakeholder_text=stakeholder_text,
                model=model,
            )

        personas_config = [
            {
                "persona": "legacy_keeper",
                "name": "Legacy Keeper",
                "priorities": "Stability, proven patterns, risk mitigation, backward compatibility",
            },
            {
                "persona": "innovator",
                "name": "Innovator",
                "priorities": "Modern architecture, scalability, cutting-edge tech, future-proofing",
            },
            {
                "persona": "mediator",
                "name": "Mediator",
                "priorities": "Balanced approach, pragmatic trade-offs, team capabilities, business value",
            },
        ]

        proposals = []
        for persona_config in personas_config:
            proposal = await self._generate_persona_proposal(
                persona=persona_config["persona"],
                persona_name=persona_config["name"],
                priorities=persona_config["priorities"],
                task=task,
                debate_history=debate_result,
                context_text=context_text,
                task_docs_text=task_docs_text,
                stakeholder_text=stakeholder_text,
                model=model,
            )
            proposals.append(proposal)

        logger.info(
            "three_proposals_generated_successfully",
            proposals_count=len(proposals),
            personas=[p["persona"] for p in proposals],
        )

        return proposals

    async def _conduct_debate_via_service(
        self,
        session: AsyncSession,
        proposal_id: int,
        acting_user_id: int,
    ) -> str:
        """
        Conduct a debate using DebateService, persisting each turn to the DB.

        Returns the debate transcript as a formatted string for use as
        context in the persona proposal generation prompts.
        """
        from app.services.debate_service import DebateService
        from app.models.user import UserRole

        logger.info(
            "debate_via_service_started",
            proposal_id=proposal_id,
            acting_user_id=acting_user_id,
        )

        debate_service = DebateService(session=session)
        debate_session = await debate_service.conduct_debate(
            proposal_id=proposal_id,
            user_id=acting_user_id,
            user_role=UserRole.ADMIN,
        )

        # Convert turn-by-turn JSONB history to the flat string format
        # expected by _generate_persona_proposal's debate_history parameter.
        history = debate_session.debate_history or []
        transcript = "\n\n".join(
            f"Turn {t.get('turn_number', i + 1)} - {t.get('persona', '').upper()}:\n{t.get('response', '')}"
            for i, t in enumerate(history)
        )

        logger.info(
            "debate_via_service_completed",
            proposal_id=proposal_id,
            turns=len(history),
            consensus=debate_session.consensus_reached,
            transcript_length=len(transcript),
        )

        return transcript

    async def _conduct_debate_inline(
        self,
        task: str,
        context_text: str,
        task_docs_text: str,
        stakeholder_text: str,
        model: Optional[str] = None,
        max_turns: int = 6,
    ) -> str:
        """
        Fallback: conduct debate as a single Claude call without DB persistence.

        Used only when proposal_id is not available (e.g. tests).
        Does NOT create a DebateSession row — the live transcript UI will
        not work for proposals generated via this path.
        """
        logger.info("inline_debate_started", max_turns=max_turns)

        debate_prompt = f"""You are facilitating a Council of Agents architectural debate.

TASK: {task}

CONTEXT:
{context_text}

DOCUMENTS:
{task_docs_text}

STAKEHOLDERS:
{stakeholder_text}

Conduct a {max_turns}-turn debate between these personas:
1. **Legacy Keeper**: Advocates for stability, proven patterns, risk mitigation
2. **Innovator**: Advocates for modern architecture, scalability, innovation
3. **Mediator**: Seeks balanced compromises

Format as:
[Turn 1 - Legacy Keeper]: <argument>
[Turn 2 - Innovator]: <counterargument>
[Turn 3 - Mediator]: <synthesis attempt>
... continue for {max_turns} turns

Focus on concrete architectural trade-offs, not philosophy."""

        debate_transcript = await self._ai_service.generate_text(
            system_prompt="You are an expert software architect facilitating multi-perspective design discussions.",
            user_prompt=debate_prompt,
            model=model,
            max_tokens=3000,
            temperature=0.8,
            operation="council_debate",
        )

        logger.info("inline_debate_completed", transcript_length=len(debate_transcript))
        return debate_transcript

    async def _generate_persona_proposal(
        self,
        persona: str,
        persona_name: str,
        priorities: str,
        task: str,
        debate_history: str,
        context_text: str,
        task_docs_text: str,
        stakeholder_text: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a single persona's architectural proposal based on debate."""
        logger.info("persona_proposal_generation_started", persona=persona_name)

        is_mediator = persona == "mediator"

        system_prompt = f"""You are the {persona_name} from the Council of Agents.

YOUR PRIORITIES: {priorities}

Based on the debate, create YOUR architectural proposal that reflects YOUR perspective.
{"CRITICAL: As Mediator, explicitly identify what each side sacrifices for consensus." if is_mediator else "Stay true to your persona's values."}"""

        user_prompt = f"""
ORIGINAL TASK:
{task}

DEBATE HISTORY:
{debate_history}

CONTEXT:
{context_text}

Generate YOUR proposal as {persona_name}. Structure as JSON:
{{
    "persona": "{persona}",
    "structured_prd": "# Proposal Title\\n\\n## Executive Summary\\n...full markdown PRD",
    "reasoning": "Why this approach aligns with my priorities",
    "trade_offs": "What I'm sacrificing and what I'm gaining",
    "confidence_score": 0-100
}}

The structured_prd should be a COMPLETE, PROFESSIONAL architectural document in Markdown format.
Include: problem statement, proposed solution, architecture diagrams (Mermaid), tech stack, risks, timeline.
""".strip()

        schema = {
            "type": "object",
            "properties": {
                "persona": {"type": "string"},
                "structured_prd": {
                    "type": "string",
                    "description": "Full markdown PRD: headings, proposed solution, tech stack, risks, timeline",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why this approach aligns with this persona's priorities",
                },
                "trade_offs": {
                    "type": "string",
                    "description": "What is being sacrificed and what is being gained",
                },
                "confidence_score": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Confidence in this proposal (0-100)",
                },
            },
            "required": [
                "persona",
                "structured_prd",
                "reasoning",
                "trade_offs",
                "confidence_score",
            ],
        }

        result = await self._ai_service.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            tool_name="submit_proposal",
            model=model,
            max_tokens=5000,
            operation=f"persona_proposal_{persona}",
        )

        result["persona"] = persona
        if not result.get("confidence_score"):
            result["confidence_score"] = 75

        logger.info(
            "persona_proposal_generated",
            persona=persona_name,
            prd_length=len(result.get("structured_prd", "")),
        )
        return result

    def _build_variation_schema(
        self, include_compromise: bool = False
    ) -> Dict[str, Any]:
        """Build JSON schema for architectural proposal."""
        base_schema = {
            "type": "object",
            "properties": {
                "persona": {"type": "string"},
                "problem_statement": {"type": "string"},
                "proposed_solution": {"type": "string"},
                "key_features": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "priority": {"type": "string", "enum": ["P0", "P1", "P2"]},
                            "desc": {"type": "string"},
                        },
                        "required": ["name", "priority", "desc"],
                    },
                },
                "technical_risks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "risk": {"type": "string"},
                            "severity": {
                                "type": "string",
                                "enum": ["Low", "Medium", "High", "Critical"],
                            },
                            "mitigation": {"type": "string"},
                        },
                        "required": ["risk", "severity", "mitigation"],
                    },
                },
                "mermaid_diagram": {"type": "string"},
                "tech_stack": {"type": "string"},
                "confidence_score": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": [
                "persona",
                "problem_statement",
                "proposed_solution",
                "key_features",
                "technical_risks",
                "tech_stack",
                "confidence_score",
            ],
        }

        if include_compromise:
            base_schema["properties"]["compromise_analysis"] = {
                "type": "object",
                "properties": {
                    "conflict_point": {"type": "string"},
                    "strategy": {"type": "string"},
                    "concession_from_legacy": {"type": "string"},
                    "concession_from_innovator": {"type": "string"},
                    "benefit_to_legacy": {"type": "string"},
                    "benefit_to_innovator": {"type": "string"},
                    "long_term_impact": {"type": "string"},
                },
                "required": [
                    "conflict_point",
                    "strategy",
                    "concession_from_legacy",
                    "concession_from_innovator",
                ],
            }
        else:
            base_schema["properties"]["compromise_analysis"] = {"type": "null"}

        return base_schema

    async def generate_single_variation(
        self,
        persona_slug: str,
        persona_name: str,
        system_instruction: str,
        task: str,
        context_text: str,
        task_docs_text: str,
        stakeholder_text: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate single architectural proposal for a persona."""
        logger.info("variation_generation_started", persona=persona_name)

        is_mediator = "mediator" in persona_slug.lower()

        compromise_instruction = (
            "CRITICAL: You are the Arbitrator. Identify what each side loses to gain consensus."
            if is_mediator
            else "Focus on your persona's specific priorities."
        )

        prompt = f"""
{system_instruction}

CONTEXT (Historical Wisdom):
{context_text}

TASK DOCUMENTS:
{task_docs_text}

STAKEHOLDERS:
{stakeholder_text}

TASK TO SOLVE:
{task}

YOUR MANDATE:
{compromise_instruction}

Provide a comprehensive proposal true to your persona's values.
""".strip()

        try:
            schema = self._build_variation_schema(include_compromise=is_mediator)

            result = await self._ai_service.generate_structured(
                system_prompt=prompt,
                user_prompt=f"Generate proposal for: {task}",
                schema=schema,
                tool_name="submit_proposal",
                model=model,
                max_tokens=4000,
            )

            result["persona"] = persona_name
            logger.info("variation_generation_success", persona=persona_name)
            return result

        except Exception as e:
            logger.error(
                "variation_generation_failed", persona=persona_slug, error=str(e)
            )
            return {
                "persona": persona_name,
                "problem_statement": f"Error: {str(e)}",
                "proposed_solution": "Generation failed",
                "confidence_score": 0,
                "key_features": [],
                "technical_risks": [],
                "mermaid_diagram": "",
                "tech_stack": "Error",
                "compromise_analysis": None,
            }

    async def generate_council_variations(
        self,
        session: AsyncSession,
        task: str,
        context_chunks: List[str],
        task_docs: List[str],
        stakeholders: List[Dict[str, str]],
        model: Optional[str] = None,
        use_caching: bool = True,
    ) -> List[Dict[str, Any]]:
        """Generate proposals from all active personas in parallel."""
        logger.info("council_generation_started", num_stakeholders=len(stakeholders))

        result = await session.exec(
            select(PromptTemplate).where(PromptTemplate.is_active)
        )
        templates = result.all()

        if not templates:
            logger.warning("no_active_templates_found")
            return []

        context_text = "\n".join([f"- {c}" for c in context_chunks])
        task_docs_text = "\n".join([f"- {d}" for d in task_docs])
        stakeholder_text = "\n".join(
            [f"- {s['name']} ({s['role']})" for s in stakeholders]
        )

        tasks = [
            self.generate_single_variation(
                persona_slug=template.slug,
                persona_name=template.name,
                system_instruction=template.system_prompt,
                task=task,
                context_text=context_text,
                task_docs_text=task_docs_text,
                stakeholder_text=stakeholder_text,
                model=model,
            )
            for template in templates
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = [r for r in results if not isinstance(r, Exception)]

        logger.info(
            "council_generation_completed",
            total=len(templates),
            successful=len(valid_results),
        )

        return valid_results


proposal_generation_service = ProposalGenerationService()
