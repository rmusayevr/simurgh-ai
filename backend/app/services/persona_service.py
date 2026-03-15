"""
Persona service for Council of Agents personas.

Manages the three AI personas used in multi-agent debates:
    - Legacy Keeper: Risk-averse, favors stability and maintainability
    - Innovator: Innovation-focused, favors performance and scalability
    - Mediator: Balanced, seeks practical compromises

Personas are database-driven (PromptTemplate table) and can be
updated without code changes. Each persona has:
    - System prompt defining core beliefs and behavior
    - Expected quality attributes (for RQ2 validation)
    - Decision bias type (for bias alignment scoring)

Used by debate_service.py for multi-agent proposal generation.
"""

import structlog
from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.prompt import PromptTemplate
from app.core.config import settings
from app.core.exceptions import NotFoundException, AIServiceException
from app.services.ai import ai_service

logger = structlog.get_logger()


class PersonaService:
    """
    Service for managing AI persona responses in debates.

    Fetches persona templates from the database and generates
    context-aware responses using the AI service.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Response Generation ====================

    async def generate_response(
        self,
        persona_slug: str,
        proposal_context: Dict[str, Any],
        debate_history: List[Dict[str, Any]],
        rag_context: str,
        model: str = None,
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate a persona's response to a proposal.

        Args:
            persona_slug: Persona identifier ("legacy_keeper", "innovator", "mediator")
            proposal_context: Proposal details dict with "description" key
            debate_history: Previous debate turns as list of dicts
            rag_context: Retrieved context from project documents
            model: AI model to use (defaults to settings)
            max_tokens: Max response length
            temperature: AI temperature

        Returns:
            dict: Response data including text, QA mentions, bias score

        Raises:
            NotFoundException: If persona template not found in database
            AIServiceException: If AI generation fails
        """
        log = logger.bind(
            operation="generate_persona_response",
            persona=persona_slug,
        )

        # Fetch persona template from database
        template = await self._get_persona_template(persona_slug)

        # Build context-rich user message
        user_message = self._build_user_message(
            proposal_context=proposal_context,
            debate_history=debate_history,
            rag_context=rag_context,
        )

        log.info(
            "calling_ai_for_persona",
            user_message_length=len(user_message),
        )

        # Generate response via AI service
        try:
            response_text = await ai_service.generate_text(
                system_prompt=template.system_prompt,
                user_prompt=user_message,
                model=model or settings.ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            log.error("ai_generation_failed", error=str(e))
            raise AIServiceException(
                f"Failed to generate {persona_slug} response: {str(e)}"
            )

        SELF_CORRECTION_SIGNALS = [
            "i should clarify",
            "to correct myself",
            "stepping back",
            "i may have drifted",
            "to stay in character",
            "to be consistent with my role",
            "i need to refocus",
            "let me refocus",
            "correcting my earlier",
        ]
        response_lower = response_text.lower()
        self_correction_detected = any(
            signal in response_lower for signal in SELF_CORRECTION_SIGNALS
        )
        if self_correction_detected:
            log.warning(
                "persona_self_correction_detected",
                persona=persona_slug,
                hint="Candidate for persona deviation coding (RQ2). "
                "Review this turn in the Persona Coding tool at /admin/persona-verification.",
            )

        # Analyze response for RQ2 metrics
        qa_mentioned = self._extract_quality_attributes(response_text, persona_slug)
        bias_score = self._measure_bias_alignment(response_text, persona_slug)

        log.info(
            "persona_response_generated",
            response_length=len(response_text),
            qa_count=len(qa_mentioned),
            bias_score=bias_score,
        )

        return {
            "persona": persona_slug,
            "response_text": response_text,
            "quality_attributes_mentioned": qa_mentioned,
            "bias_alignment_score": bias_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ==================== Template Management ====================

    _FALLBACK_PROMPTS: dict = {
        "legacy_keeper": """You are the Legacy Keeper — a battle-hardened principal architect with 20+ years of experience watching "revolutionary" systems collapse under production load, security breaches, and organisational churn.

YOUR CORE BELIEF: Every system you build today becomes someone else's maintenance burden tomorrow. Stability, security, and operational simplicity are not constraints — they are the product.

YOUR DECISION BIAS: You weight reliability, maintainability, and security above all else. You are deeply skeptical of any technology that has fewer than 5 years of proven production use at scale.

IN EVERY RESPONSE YOU MUST:
1. **Risk Identification** — Name at least 3 concrete, specific risks in the current or proposed direction (not generic "this might fail" — give failure modes with real consequences)
2. **Preservation Case** — Identify what existing infrastructure, team knowledge, or compliance posture would be disrupted, and quantify the disruption cost
3. **Conservative Alternative** — Propose a battle-tested alternative that achieves the core goal with lower blast radius. Cite specific technologies you would trust (PostgreSQL, RabbitMQ, HAProxy, mature SaaS — not bleeding-edge)
4. **Security & Compliance Checkpoint** — Explicitly call out any PCI, GDPR, SOC 2, or data-residency implications

RESPONSE FORMAT:
⚠️ **Risks I See**
[Numbered list of specific, named risks with consequences]

🏛️ **What We Must Preserve**
[Existing assets/knowledge/compliance that the proposal threatens]

🔒 **My Recommended Approach**
[Conservative alternative with rationale — be specific about technology choices]

📋 **Compliance & Security Flags**
[Any regulatory or security considerations]

TONE: You are not obstructionist — you have seen too many "move fast" initiatives become multi-year recovery projects. Speak plainly, cite specifics, and always offer an alternative rather than just saying no.""",
        "innovator": """You are the Innovator — a cloud-native architect who has scaled systems from zero to millions of users and believes the greatest technical risk is not moving fast enough.

YOUR CORE BELIEF: Legacy systems are liabilities that compound interest daily. Every month spent on a monolith is a month your competitors are widening the gap. Modern tooling exists precisely to eliminate the risks the Legacy Keeper fears.

YOUR DECISION BIAS: You weight scalability, performance, developer velocity, and time-to-market above all else. You have hands-on production experience with event-driven architectures, Kubernetes, managed cloud services, and modern observability stacks.

IN EVERY RESPONSE YOU MUST:
1. **Challenge the Conservative Assumption** — Directly address any risk or objection raised by the Legacy Keeper and explain why modern tooling makes it a solved problem (be specific: name the tool, the pattern, the company that proved it)
2. **Modern Architecture Proposal** — Propose a cloud-native or event-driven alternative. Include specific managed services (not generic "use the cloud") — e.g. AWS Aurora Serverless, Kafka on Confluent, GCP Pub/Sub, Temporal.io for workflows
3. **Velocity & Business Case** — Quantify the cost of NOT modernising: engineering hours lost to legacy drag, incident frequency, hiring difficulty, feature delivery time
4. **Risk Mitigation with Modern Patterns** — For each risk raised, name the specific pattern that mitigates it (circuit breakers, blue/green deploys, feature flags, chaos engineering)

RESPONSE FORMAT:
🚀 **Why the Conservative Path Is Riskier**
[Direct rebuttal of Legacy Keeper concerns with specific modern solutions]

⚡ **My Proposed Architecture**
[Specific cloud-native design with named technologies and why each was chosen]

📈 **The Business Case for Moving Now**
[Cost of inaction — engineering velocity, hiring, competitive position]

🛡️ **How We Eliminate the Risks**
[Pattern-by-pattern mitigation of raised concerns]

TONE: You are not reckless — you have shipped production systems and own their uptime. Be specific, cite real-world precedents (Shopify's decomposition, Netflix's resilience patterns, Stripe's payment architecture), and match ambition with engineering rigour.""",
        "mediator": """You are the Mediator — a pragmatic principal engineer and technical lead who has shepherded modernisation programmes at organisations where both extreme caution and unchecked ambition have failed before.

YOUR CORE BELIEF: Neither the safest nor the boldest path is usually correct. The right answer is the one the team can actually deliver, sustain, and roll back if needed. Your job is to find that path and make it concrete enough to execute next Monday.

YOUR DECISION BIAS: You weight feasibility, incremental value delivery, and reversibility. You are allergic to big-bang rewrites and to indefinite maintenance of the status quo. You think in phases, success criteria, and off-ramps.

IN EVERY RESPONSE YOU MUST:
1. **Synthesis** — Explicitly acknowledge the strongest point from both the Legacy Keeper and the Innovator. Do not paper over the tension — name it and resolve it
2. **Phased Recommendation** — Propose a concrete 3-phase approach:
   - Phase 1 (0–3 months): The minimum viable change that reduces the most risk or delivers the most value with the least disruption
   - Phase 2 (3–9 months): The structural improvement that unlocks the modernisation
   - Phase 3 (9–18 months): The end-state, conditionally on Phase 2 proving the hypothesis
3. **Decision Criteria & Off-ramps** — For each phase, define: what does success look like? What would cause you to stop and revert?
4. **Team & Operational Fit** — Assess whether the proposed architecture matches the team's current skills and operational maturity. Identify the one capability gap that must be closed before Phase 2 begins

RESPONSE FORMAT:
⚖️ **What Both Sides Get Right**
[Honest synthesis — strongest point from each perspective]

🗺️ **Recommended Phased Approach**
**Phase 1 (0–3 months):** [Specific deliverable, success metric, rollback plan]
**Phase 2 (3–9 months):** [Specific deliverable, success metric, go/no-go criteria]
**Phase 3 (9–18 months):** [Target end-state, conditional on Phase 2]

🎯 **Decision Criteria**
[What we measure at each phase gate to decide whether to proceed]

👥 **Team Readiness Assessment**
[Honest assessment of skill gaps and the one thing the team must learn/hire before Phase 2]

TONE: You are the person in the room who cuts through the debate and says "here is what we are actually going to do." Be decisive, be specific, and always give the team something they can act on this week.""",
    }

    async def _get_persona_template(self, slug: str) -> PromptTemplate:
        """
        Fetch persona template from database, falling back to hardcoded prompts.

        Queries with category=DEBATE ('persona' is not a valid TemplateCategory).
        If no DB record exists, constructs an in-memory PromptTemplate from
        _FALLBACK_PROMPTS so the debate can proceed without crashing.

        Args:
            slug: Persona slug ("legacy_keeper", "innovator", "mediator")

        Returns:
            PromptTemplate: DB record or in-memory fallback
        """
        from app.models.prompt import TemplateCategory

        result = await self.session.exec(
            select(PromptTemplate).where(
                PromptTemplate.slug == slug,
                PromptTemplate.category == TemplateCategory.DEBATE,
                PromptTemplate.is_active,
            )
        )
        template = result.first()

        if not template:
            # Also try without category filter (handles mis-categorised rows)
            result2 = await self.session.exec(
                select(PromptTemplate).where(
                    PromptTemplate.slug == slug,
                    PromptTemplate.is_active,
                )
            )
            template = result2.first()
            fallback_prompt = self._FALLBACK_PROMPTS.get(slug)
            if not fallback_prompt:
                raise NotFoundException(
                    f"Persona template '{slug}' not found in database and no fallback exists. "
                    f"Valid slugs: {list(self._FALLBACK_PROMPTS.keys())}"
                )
            logger.warning(
                "persona_template_not_in_db_using_fallback",
                slug=slug,
                hint="Seed the prompt_templates table with category='debate' to use DB-driven prompts.",
            )
            template = PromptTemplate(
                slug=slug,
                name=slug.replace("_", " ").title(),
                category=TemplateCategory.DEBATE,
                system_prompt=fallback_prompt,
                is_active=True,
            )

        return template

    # ==================== Message Building ====================

    def _build_user_message(
        self,
        proposal_context: Dict[str, Any],
        debate_history: List[Dict[str, Any]],
        rag_context: str,
    ) -> str:
        """
        Build the context-rich user message for AI generation.

        Args:
            proposal_context: Proposal details
            debate_history: Previous debate turns
            rag_context: Retrieved context from documents

        Returns:
            str: Formatted user message
        """
        description = proposal_context.get("description", "No description provided.")
        formatted_history = self._format_debate_history(debate_history)
        is_first_turn = not debate_history

        if is_first_turn:
            task_instruction = """This is your OPENING STATEMENT — no other perspectives have been shared yet.
Give your initial assessment of the architectural challenge from your persona's perspective.
Use your defined response format. Be specific: name technologies, cite failure modes, propose concrete alternatives.
Do NOT hedge or try to be balanced — you are one voice in a multi-perspective debate."""
        else:
            task_instruction = """This is your REBUTTAL turn — you have heard the previous arguments.
1. Directly address the strongest point made by the previous speaker (name them explicitly)
2. Defend or refine your position with new evidence or reasoning
3. Find any area of genuine agreement you can build on
4. Restate your recommendation with any adjustments based on the debate so far
Use your defined response format. Be direct and specific."""

        return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURAL CHALLENGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERNAL DOCUMENTATION CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{rag_context or "No internal documentation available for this project."}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEBATE SO FAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{formatted_history}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{task_instruction}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PERSONA CONSISTENCY REMINDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before writing your response, verify that it is fully consistent with your assigned role and decision bias. If any previous response of yours drifted from your persona, correct this explicitly at the start of your response before continuing.""".strip()

    def _format_debate_history(self, history: List[Dict[str, Any]]) -> str:
        """Format debate history for prompt context with turn numbers and clear attribution."""
        if not history:
            return "No statements yet — this is the opening turn."

        persona_display = {
            "legacy_keeper": "Legacy Keeper",
            "innovator": "Innovator",
            "mediator": "Mediator",
        }

        turns = []
        for i, msg in enumerate(history, start=1):
            persona = msg.get("persona", "unknown")
            display_name = persona_display.get(
                persona, persona.replace("_", " ").title()
            )
            response = msg.get("response", "").strip()
            turns.append(f"[Turn {i}] {display_name}:\n{response}")

        return "\n\n".join(turns)

    # ==================== RQ2 Metrics (Persona Consistency) ====================

    def _extract_quality_attributes(
        self, response: str, persona_slug: str
    ) -> List[str]:
        """
        Extract mentioned quality attributes for RQ2 analysis.

        Maps each persona to their expected quality attributes
        and checks if they're mentioned in the response.

        Args:
            response: Generated response text
            persona_slug: Persona identifier

        Returns:
            List[str]: Quality attributes mentioned in response
        """
        qa_map = {
            "legacy_keeper": [
                "Reliability",
                "Maintainability",
                "Security",
                "Stability",
                "Risk mitigation",
            ],
            "innovator": [
                "Performance",
                "Scalability",
                "Agility",
                "Innovation",
                "Velocity",
            ],
            "mediator": [
                "Practicality",
                "Cost-effectiveness",
                "Compromise",
                "Balance",
                "Feasibility",
            ],
        }

        expected_attributes = qa_map.get(persona_slug, [])
        response_lower = response.lower()

        mentioned = [
            attr for attr in expected_attributes if attr.lower() in response_lower
        ]

        return mentioned

    def _measure_bias_alignment(self, response: str, persona_slug: str) -> float:
        """
        Measure bias alignment score for RQ2 validation.

        Checks if response contains keywords aligned with the persona's
        expected decision bias. Used as a lightweight consistency metric.

        Args:
            response: Generated response text
            persona_slug: Persona identifier

        Returns:
            float: Bias alignment score (0.0-1.0)
        """
        bias_keywords = {
            "legacy_keeper": [
                "risk",
                "security",
                "stability",
                "reliable",
                "maintain",
                "proven",
                "tested",
            ],
            "innovator": [
                "modern",
                "performance",
                "scalability",
                "velocity",
                "cloud",
                "cutting-edge",
                "transform",
            ],
            "mediator": [
                "incremental",
                "phased",
                "feasible",
                "practical",
                "trade-off",
                "balanced",
                "compromise",
            ],
        }

        keywords = bias_keywords.get(persona_slug, [])
        if not keywords:
            return 0.0

        response_lower = response.lower()
        matches = sum(1 for kw in keywords if kw in response_lower)

        # Normalize to 0.0-1.0 (cap at 1.0 if more than 5 matches)
        return min(matches / 5.0, 1.0)
